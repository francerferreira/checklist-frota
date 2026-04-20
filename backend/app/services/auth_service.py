from __future__ import annotations

from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.models import User


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="auth-token")


def generate_token(user: User) -> str:
    return _serializer().dumps({"user_id": user.id, "tipo": user.tipo})


def verify_token(token: str) -> User | None:
    try:
        payload = _serializer().loads(
            token,
            max_age=current_app.config["TOKEN_MAX_AGE_SECONDS"],
        )
    except (BadSignature, SignatureExpired):
        return None

    user = User.query.get(payload.get("user_id"))
    if not user or not user.ativo:
        return None
    return user


def user_has_management_access(user: User) -> bool:
    return user.tipo in {"admin", "gestor"}


def user_can_resolve_non_conformity(user: User) -> bool:
    return user.tipo in {"admin", "gestor", "mecanico"}


def user_has_mechanic_workspace_access(user: User) -> bool:
    return user.tipo in {"admin", "gestor", "mecanico"}


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.replace("Bearer ", "").strip()
        user = verify_token(token) if token else None
        if not user:
            return jsonify({"error": "Nao autorizado."}), 401

        g.current_user = user
        return view(*args, **kwargs)

    return wrapped
