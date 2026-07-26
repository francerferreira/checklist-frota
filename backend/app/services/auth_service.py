from __future__ import annotations

from datetime import timedelta
from functools import wraps
from secrets import token_urlsafe

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models import RevokedToken, User
from app.utils.timezone import now_manaus_naive


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="auth-token")


def generate_token(user: User) -> str:
    return _serializer().dumps({"user_id": user.id, "tipo": user.tipo, "jti": token_urlsafe(32)})


def _load_token_payload(token: str) -> dict | None:
    try:
        return _serializer().loads(token, max_age=current_app.config["TOKEN_MAX_AGE_SECONDS"])
    except (BadSignature, SignatureExpired):
        return None


def verify_token(token: str) -> User | None:
    payload = _load_token_payload(token)
    if not payload:
        return None

    jti = str(payload.get("jti") or "").strip()
    if jti and RevokedToken.query.filter_by(jti=jti).first():
        return None
    user = db.session.get(User, payload.get("user_id"))
    if not user or not user.ativo:
        return None
    return user


def revoke_token(token: str, *, user_id: int) -> bool:
    payload = _load_token_payload(token)
    jti = str((payload or {}).get("jti") or "").strip()
    RevokedToken.query.filter(RevokedToken.expires_at < now_manaus_naive()).delete(synchronize_session=False)
    if not jti or RevokedToken.query.filter_by(jti=jti).first():
        return False
    db.session.add(
        RevokedToken(
            jti=jti,
            user_id=user_id,
            expires_at=now_manaus_naive() + timedelta(seconds=current_app.config["TOKEN_MAX_AGE_SECONDS"]),
        )
    )
    return True


def user_has_management_access(user: User) -> bool:
    return user.tipo in {"admin", "gestor"}


def user_can_resolve_non_conformity(user: User) -> bool:
    return user.tipo in {"admin", "gestor", "mecanico", "operacional"}


def user_has_mechanic_workspace_access(user: User) -> bool:
    return user.tipo in {"admin", "gestor", "mecanico", "operacional"}


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.replace("Bearer ", "").strip()
        user = verify_token(token) if token else None
        if not user:
            return jsonify({"error": "Nao autorizado."}), 401

        g.current_user = user
        g.auth_token = token
        return view(*args, **kwargs)

    return wrapped
