from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.services.auth_service import auth_required, user_has_management_access

bp = Blueprint("users", __name__)
VALID_USER_TYPES = {"admin", "gestor", "motorista", "mecanico"}


def _guard_management_access():
    if g.current_user.tipo != "admin":
        return jsonify({"error": "Somente admin pode gerenciar logins."}), 403
    return None


@bp.get("/usuarios")
@auth_required
def list_users():
    denied = _guard_management_access()
    if denied:
        return denied

    return jsonify([user.to_dict() for user in User.query.order_by(User.nome.asc()).all()])


@bp.get("/usuarios/mecanicos")
@auth_required
def list_mechanics():
    if not user_has_management_access(g.current_user):
        return jsonify({"error": "Somente admin ou gestor podem consultar mecanicos."}), 403
    users = User.query.filter_by(tipo="mecanico", ativo=True).order_by(User.nome.asc()).all()
    return jsonify([user.to_dict() for user in users])


@bp.put("/usuarios/me/senha")
@auth_required
def update_own_password():
    payload = request.get_json(silent=True) or {}
    current_password = payload.get("senha_atual") or ""
    new_password = payload.get("nova_senha") or ""

    if not current_password or not new_password:
        return jsonify({"error": "Informe a senha atual e a nova senha."}), 400
    if len(new_password) < 6:
        return jsonify({"error": "A nova senha deve ter pelo menos 6 caracteres."}), 400
    if not g.current_user.check_password(current_password):
        return jsonify({"error": "Senha atual invalida."}), 401

    g.current_user.set_password(new_password)
    db.session.commit()
    return jsonify({"success": True})


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
        return jsonify({"error": f"Campos obrigatorios ausentes: {', '.join(missing)}"}), 400

    user = User(
        nome=payload["nome"].strip(),
        login=payload["login"].strip().lower(),
        tipo=payload["tipo"].strip().lower(),
        ativo=bool(payload.get("ativo", True)),
    )
    if user.tipo not in VALID_USER_TYPES:
        return jsonify({"error": "Tipo de usuario invalido."}), 400
    user.set_password(payload["senha"])
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Login ja cadastrado."}), 409
    return jsonify(user.to_dict()), 201


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
            return jsonify({"error": "Tipo de usuario invalido."}), 400
        user.tipo = tipo
    if "ativo" in payload:
        if user.id == g.current_user.id and not payload["ativo"]:
            return jsonify({"error": "Nao e permitido desativar o proprio login."}), 400
        user.ativo = bool(payload["ativo"])
    if payload.get("senha"):
        user.set_password(payload["senha"])

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Login ja cadastrado."}), 409

    return jsonify(user.to_dict())


@bp.delete("/usuarios/<int:user_id>")
@auth_required
def delete_user(user_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)

    if user.id == g.current_user.id:
        return jsonify({"error": "Nao e permitido excluir o proprio login."}), 400

    if user.tipo == "admin":
        total_admins = User.query.filter_by(tipo="admin", ativo=True).count()
        if total_admins <= 1:
            return jsonify({"error": "Nao e permitido excluir o ultimo administrador ativo."}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})
