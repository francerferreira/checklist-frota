from flask import Blueprint, g, request

from app.extensions import db
from app.models import User
from app.services.audit_service import record_event, record_login_event, record_logout_event
from app.services.auth_service import auth_required, generate_token
from app.utils.responses import api_response

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    login_value = (payload.get("login") or "").strip().lower()
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
    db.session.commit()
    return api_response(
        True,
        data={
            "token": generate_token(user),
            "user": user.to_dict(),
        },
    )


@bp.post("/logout")
@auth_required
def logout():
    record_logout_event(g.current_user)
    db.session.commit()
    return api_response(True, data={"message": "Sessao encerrada."})
