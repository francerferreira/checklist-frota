import hmac

from flask import Blueprint, current_app, g, request

from app.extensions import db
from app.services.auth_service import auth_required, user_has_management_access
from app.services.maintenance_intelligence_service import acknowledge_automation_alert, evaluate_automation_rules, list_automation_alerts
from app.utils.responses import api_response


bp = Blueprint("intelligence", __name__, url_prefix="/inteligencia")


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar automacoes.", status_code=403)
    return None


@bp.get("/automacoes")
@auth_required
def automation_list():
    denied = _guard_management()
    return denied or api_response(True, data=list_automation_alerts())


@bp.post("/automacoes/avaliar")
@auth_required
def automation_evaluate():
    denied = _guard_management()
    return denied or api_response(True, data=evaluate_automation_rules(user_id=g.current_user.id))


@bp.post("/automacoes/executar-agendada")
def automation_scheduled_evaluate():
    expected_token = str(current_app.config.get("AUTOMATION_JOB_TOKEN") or "").strip()
    received_token = str(request.headers.get("X-Automation-Token") or "").strip()
    if not expected_token:
        return api_response(False, error="Agendamento de automacao nao configurado.", status_code=503)
    if not hmac.compare_digest(received_token, expected_token):
        return api_response(False, error="Nao autorizado.", status_code=401)
    return api_response(True, data=evaluate_automation_rules(user_id=None, source="AGENDADA"))


@bp.put("/automacoes/<int:alert_id>/reconhecer")
@auth_required
def automation_acknowledge(alert_id: int):
    denied = _guard_management()
    if denied:
        return denied
    try:
        return api_response(True, data=acknowledge_automation_alert(alert_id, user_id=g.current_user.id).to_dict())
    except LookupError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
