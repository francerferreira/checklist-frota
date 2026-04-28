from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.services.auth_service import auth_required, user_has_management_access
from app.utils.responses import api_response

bp = Blueprint("users", __name__)
VALID_USER_TYPES = {"admin", "gestor", "motorista", "mecanico"}


def _guard_management_access():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente admin pode gerenciar logins.", status_code=403)
    return None


@bp.get("/usuarios")
@auth_required
def list_users():
    denied = _guard_management_access()
    if denied:
        return denied

    return api_response(True, data=[user.to_dict() for user in User.query.order_by(User.nome.asc()).all()])


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


@bp.post("/usuarios")
@auth_required
def create_user():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    required_fields = ["nome", "login", "senha", "tipo"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return api_response(False, error=f"Campos obrigatorios ausentes: {', '.join(missing)}", status_code=400)

    user = User(
        nome=payload["nome"].strip(),
        login=payload["login"].strip().lower(),
        tipo=payload["tipo"].strip().lower(),
        ativo=bool(payload.get("ativo", True)),
    )
    if user.tipo not in VALID_USER_TYPES:
        return api_response(False, error="Tipo de usuario invalido.", status_code=400)
    user.set_password(payload["senha"])
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Login ja cadastrado.", status_code=409)
    return api_response(True, data=user.to_dict(), status_code=201)


@bp.put("/usuarios/<int:user_id>")
@auth_required
def update_user(user_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}

    if payload.get("nome"):
        user.nome = payload["nome"].strip()
    if payload.get("login"):
        user.login = payload["login"].strip().lower()
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
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Login ja cadastrado.", status_code=409)

    return api_response(True, data=user.to_dict())


@bp.delete("/usuarios/<int:user_id>")
@auth_required
def delete_user(user_id: int):
    denied = _guard_management_access()
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
