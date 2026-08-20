import base64
import binascii
import json
import re
import uuid
from pathlib import Path

from flask import Blueprint, current_app, g, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AuditLog, Employee, User, UserPagePermission
from app.services.auth_service import auth_required, user_has_management_access
from app.services.audit_service import record_event
from app.services.identity_service import normalize_login
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive

bp = Blueprint("users", __name__)
VALID_USER_TYPES = {"admin", "gestor", "motorista", "mecanico", "operacional"}


def _guard_admin_access():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente admin pode gerenciar logins.", status_code=403)
    return None


def _session_activity_by_user(user_ids: list[int]) -> dict[int, dict]:
    """Resume a última entrada e a sessão atual sem armazenar senha ou token."""
    if not user_ids:
        return {}
    logs = AuditLog.query.filter(
        AuditLog.user_id.in_(user_ids),
        AuditLog.entity_type == "SESSION",
        AuditLog.action.in_({"LOGIN_SUCCESS", "LOGOUT"}),
    ).order_by(AuditLog.created_at.asc()).all()
    activity = {
        user_id: {
            "last_login_at": None,
            "last_logout_at": None,
            "last_login_ip": None,
            "session_open": False,
            "session_duration_seconds": 0,
        }
        for user_id in user_ids
    }
    for log in logs:
        row = activity.setdefault(log.user_id, {
            "last_login_at": None,
            "last_logout_at": None,
            "last_login_ip": None,
            "session_open": False,
            "session_duration_seconds": 0,
        })
        if log.action == "LOGIN_SUCCESS":
            row["last_login_at"] = log.created_at
            try:
                payload = json.loads(log.new_value or "{}")
            except (TypeError, ValueError):
                payload = {}
            row["last_login_ip"] = payload.get("ip")
        elif log.action == "LOGOUT":
            row["last_logout_at"] = log.created_at

    now = now_manaus_naive()
    for row in activity.values():
        login_at = row["last_login_at"]
        logout_at = row["last_logout_at"]
        is_open = bool(login_at and (not logout_at or login_at > logout_at))
        end_at = now if is_open else logout_at
        row["session_open"] = is_open
        row["session_duration_seconds"] = max(0, int((end_at - login_at).total_seconds())) if login_at and end_at else 0
        for key in ("last_login_at", "last_logout_at"):
            if row[key]:
                row[key] = row[key].isoformat()
    return activity


def _user_with_activity(user: User, activity: dict) -> dict:
    payload = user.to_dict()
    payload.update(activity)
    return payload


@bp.get("/usuarios")
@auth_required
def list_users():
    denied = _guard_admin_access()
    if denied:
        return denied

    query = User.query
    if search := str(request.args.get("q") or "").strip():
        pattern = f"%{search}%"
        query = query.filter((User.nome.ilike(pattern)) | (User.login.ilike(pattern)))
    if status := str(request.args.get("status") or "").strip().upper():
        if status in {"ATIVO", "INATIVO"}:
            query = query.filter(User.ativo.is_(status == "ATIVO"))
    users = query.order_by(User.nome.asc()).all()
    activity = _session_activity_by_user([user.id for user in users])
    return api_response(True, data=[_user_with_activity(user, activity.get(user.id, {})) for user in users])


@bp.get("/usuarios/<int:user_id>/perfil")
@auth_required
def get_user_profile(user_id: int):
    denied = _guard_admin_access()
    if denied:
        return denied
    user = User.query.get_or_404(user_id)
    activity = _session_activity_by_user([user.id]).get(user.id, {})
    return api_response(True, data=_user_with_activity(user, activity))


@bp.post("/usuarios/<int:user_id>/reset-primeiro-acesso")
@auth_required
def reset_user_first_access(user_id: int):
    denied = _guard_admin_access()
    if denied:
        return denied
    user = User.query.get_or_404(user_id)
    employee = Employee.query.filter_by(user_id=user.id).first()
    if not employee:
        return api_response(False, error="Este login nao esta vinculado a um colaborador.", status_code=404)
    # Os arquivos antigos permanecem no armazenamento para preservar auditoria.
    employee.photo_path = None
    employee.signature_path = None
    employee.first_access_completed_at = None
    db.session.commit()
    return api_response(True, data=user.to_dict())


@bp.put("/usuarios/<int:user_id>/telas")
@auth_required
def update_user_pages(user_id: int):
    denied = _guard_admin_access()
    if denied:
        return denied
    user = User.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}
    requested = payload.get("page_keys")
    if not isinstance(requested, list):
        return api_response(False, error="Informe uma lista de telas.", status_code=400)
    # Importacao local evita acoplamento de inicializacao entre os blueprints.
    from app.routes.navigation import ROLE_PAGES

    allowed = ROLE_PAGES.get(str(user.tipo or "").strip().lower(), {"dashboard"})
    selected = {str(page).strip() for page in requested if str(page).strip()}
    invalid = sorted(selected - allowed)
    if invalid:
        return api_response(False, error=f"Telas nao permitidas para este perfil: {', '.join(invalid)}", status_code=400)
    selected.add("dashboard")
    rows = {row.page_key: row for row in user.page_permissions}
    for page_key in selected:
        row = rows.get(page_key)
        if row is None:
            db.session.add(UserPagePermission(user_id=user.id, page_key=page_key, enabled=True))
        else:
            row.enabled = True
    for page_key, row in rows.items():
        if page_key not in selected:
            row.enabled = False
    db.session.commit()
    return api_response(True, data=user.to_dict())


@bp.get("/usuarios/mecanicos")
@auth_required
def list_mechanics():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem consultar mecanicos.", status_code=403)
    users = User.query.filter_by(tipo="mecanico", ativo=True).order_by(User.nome.asc()).all()
    return api_response(True, data=[user.to_dict() for user in users])


@bp.put("/usuarios/me/senha")
@auth_required
def update_own_password():
    payload = request.get_json(silent=True) or {}
    current_password = payload.get("senha_atual") or ""
    new_password = payload.get("nova_senha") or ""

    if not current_password or not new_password:
        return api_response(False, error="Informe a senha atual e a nova senha.", status_code=400)
    if len(new_password) < 6:
        return api_response(False, error="A nova senha deve ter pelo menos 6 caracteres.", status_code=400)
    if not g.current_user.check_password(current_password):
        return api_response(False, error="Senha atual invalida.", status_code=401)

    g.current_user.set_password(new_password)
    db.session.commit()
    return api_response(True, data={"message": "Senha atualizada com sucesso."})


def _save_data_url(data_url: str, prefix: str) -> str:
    match = re.match(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", str(data_url or ""), re.I | re.S)
    if not match:
        raise ValueError("Imagem inválida. Envie PNG, JPG ou WEBP.")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Imagem inválida.") from exc
    if not content or len(content) > 5 * 1024 * 1024:
        raise ValueError("A imagem deve ter até 5 MB.")
    extension = "jpg" if match.group(1).lower() in {"image/jpeg", "image/jpg"} else match.group(1).split("/")[-1].lower()
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "identidade"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}.{extension}"
    (folder / filename).write_bytes(content)
    return f"/uploads/identidade/{filename}"


@bp.post("/usuarios/me/primeiro-acesso")
@auth_required
def complete_first_access():
    employee = Employee.query.filter_by(user_id=g.current_user.id).first()
    if not employee:
        return api_response(False, error="Este login não está vinculado a um colaborador.", status_code=404)
    payload = request.get_json(silent=True) or {}
    try:
        photo_path = _save_data_url(payload.get("foto_data_url"), f"foto_{employee.registration}")
        signature_path = _save_data_url(payload.get("assinatura_data_url"), f"assinatura_{employee.registration}")
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    employee.photo_path = photo_path
    employee.signature_path = signature_path
    employee.first_access_completed_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data={"message": "Primeiro acesso concluído.", "employee": employee.to_dict()})


@bp.post("/usuarios")
@auth_required
def create_user():
    denied = _guard_admin_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    required_fields = ["nome", "login", "senha", "tipo"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return api_response(False, error=f"Campos obrigatorios ausentes: {', '.join(missing)}", status_code=400)

    user = User(
        nome=payload["nome"].strip(),
        login=normalize_login(payload["login"]),
        tipo=payload["tipo"].strip().lower(),
        ativo=bool(payload.get("ativo", True)),
    )
    if user.tipo not in VALID_USER_TYPES:
        return api_response(False, error="Tipo de usuario invalido.", status_code=400)
    user.set_password(payload["senha"])
    db.session.add(user)
    try:
        db.session.flush()
        record_event(user_id=g.current_user.id, entity_type="USER", entity_id=user.id, action="CREATED", new_value=user.to_dict())
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Login ja cadastrado.", status_code=409)
    return api_response(True, data=user.to_dict(), status_code=201)


@bp.put("/usuarios/<int:user_id>")
@auth_required
def update_user(user_id: int):
    denied = _guard_admin_access()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}

    if payload.get("nome"):
        user.nome = payload["nome"].strip()
    if payload.get("login"):
        user.login = normalize_login(payload["login"])
    if payload.get("tipo"):
        tipo = payload["tipo"].strip().lower()
        if tipo not in VALID_USER_TYPES:
            return api_response(False, error="Tipo de usuario invalido.", status_code=400)
        user.tipo = tipo
    if "ativo" in payload:
        if user.id == g.current_user.id and not payload["ativo"]:
            return api_response(False, error="Nao e permitido desativar o proprio login.", status_code=400)
        user.ativo = bool(payload["ativo"])
    if payload.get("senha"):
        user.set_password(payload["senha"])

    try:
        record_event(user_id=g.current_user.id, entity_type="USER", entity_id=user.id, action="UPDATED", new_value=user.to_dict())
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Login ja cadastrado.", status_code=409)

    activity = _session_activity_by_user([user.id]).get(user.id, {})
    return api_response(True, data=_user_with_activity(user, activity))


@bp.delete("/usuarios/<int:user_id>")
@auth_required
def delete_user(user_id: int):
    denied = _guard_admin_access()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)

    if user.id == g.current_user.id:
        return api_response(False, error="Nao e permitido excluir o proprio login.", status_code=400)

    if user.tipo == "admin":
        total_admins = User.query.filter_by(tipo="admin", ativo=True).count()
        if total_admins <= 1:
            return api_response(False, error="Nao e permitido excluir o ultimo administrador ativo.", status_code=400)

    db.session.delete(user)
    db.session.commit()
    return api_response(True, data={"message": "Usuario excluido."})
