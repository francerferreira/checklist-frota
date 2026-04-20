from flask import Blueprint, jsonify, request

from app.models import User
from app.services.auth_service import generate_token

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    login_value = (payload.get("login") or "").strip().lower()
    password = payload.get("senha") or ""

    user = User.query.filter_by(login=login_value).first()
    if not user or not user.ativo or not user.check_password(password):
        return jsonify({"error": "Login ou senha invalidos."}), 401

    return jsonify(
        {
            "token": generate_token(user),
            "user": user.to_dict(),
        }
    )
