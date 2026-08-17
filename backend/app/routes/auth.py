from flask import Blueprint, g, request

from app.extensions import db
from app.models import PasswordResetRequest, User
from app.services.audit_service import record_event, record_login_event, record_logout_event
from app.services.auth_service import auth_required, generate_token, revoke_token
from app.services.identity_service import normalize_login
from app.services.notification_service import create_notification
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    login_value = normalize_login(payload.get("login"))
    password = payload.get("senha") or ""

    user = User.query.filter_by(login=login_value).first()
    if not user or not user.ativo or not user.check_password(password):
        if user:
            record_login_event(user, success=False)
        else:
            record_event(
                user_id=None,
                entity_type="SESSION",
                entity_id=0,
                action="LOGIN_FAILED",
                new_value=f"login={login_value or '-'}",
            )
        db.session.commit()
        return api_response(False, error="Login ou senha invalidos.", status_code=401)

    record_login_event(user, success=True)
    create_notification(
        user_id=user.id,
        title="Acesso realizado",
        message="Sua sessão no SIS MMP foi iniciada.",
        priority="SUCCESS",
        origin="AUTH",
        entity_type="SESSION",
        entity_id=user.id,
    )
    db.session.commit()
    return api_response(
        True,
        data={
            "token": generate_token(user),
            "user": user.to_dict(),
            "first_access_required": bool(
                user.employee and (not user.employee.photo_path or not user.employee.signature_path)
            ),
        },
    )


@bp.post("/auth/reset-solicitacoes")
def request_password_reset():
    payload = request.get_json(silent=True) or {}
    requested_login = normalize_login(payload.get("login"))
    if not requested_login:
        return api_response(False, error="Informe o usuário para solicitar o reset.", status_code=400)
    user = User.query.filter_by(login=requested_login).first()
    pending = PasswordResetRequest.query.filter_by(requested_login=requested_login, status="PENDENTE").first()
    if not pending:
        db.session.add(
            PasswordResetRequest(
                user_id=user.id if user else None,
                requested_login=requested_login,
                status="PENDENTE",
            )
        )
        db.session.commit()
    # Não revela se o login existe: evita descoberta de contas.
    return api_response(True, data={"message": "Solicitação enviada ao administrador."})


@bp.get("/auth/reset-solicitacoes")
@auth_required
def list_password_reset_requests():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente admin pode consultar solicitações de reset.", status_code=403)
    rows = PasswordResetRequest.query.order_by(PasswordResetRequest.requested_at.desc()).limit(100).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.post("/auth/reset-solicitacoes/<int:request_id>/atender")
@auth_required
def resolve_password_reset(request_id: int):
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente admin pode atender reset de senha.", status_code=403)
    row = db.session.get(PasswordResetRequest, request_id)
    if not row or row.status != "PENDENTE":
        return api_response(False, error="Solicitação de reset não encontrada ou já atendida.", status_code=404)
    payload = request.get_json(silent=True) or {}
    new_password = str(payload.get("nova_senha") or "").strip()
    if len(new_password) < 6:
        return api_response(False, error="Informe uma nova senha com pelo menos 6 caracteres.", status_code=400)
    user = row.user or User.query.filter_by(login=row.requested_login).first()
    if not user:
        row.status = "ATENDIDO"
        row.resolved_by_user_id = g.current_user.id
        row.resolved_at = now_manaus_naive()
        row.notes = "Login não localizado; solicitação encerrada pelo administrador."
    else:
        user.set_password(new_password)
        row.user_id = user.id
        row.status = "ATENDIDO"
        row.resolved_by_user_id = g.current_user.id
        row.resolved_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data={"message": "Reset atendido com sucesso."})


@bp.post("/logout")
@auth_required
def logout():
    revoke_token(g.auth_token, user_id=g.current_user.id)
    record_logout_event(g.current_user)
    db.session.commit()
    return api_response(True, data={"message": "Sessao encerrada."})
