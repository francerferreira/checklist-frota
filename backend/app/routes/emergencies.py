from flask import Blueprint, g, request

from app.extensions import db
from app.services.auth_service import auth_required, user_has_management_access, user_has_mechanic_workspace_access
from app.services.emergency_service import (
    complete_repair,
    convert_emergency_to_work_order,
    create_emergency,
    get_emergency,
    get_work_order,
    list_emergencies,
    record_operational_test,
    release_work_order,
    start_work_order,
    triage_emergency,
)
from app.utils.responses import api_response


bp = Blueprint("emergencies", __name__)


def _management_guard():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem realizar esta acao.", status_code=403)


def _workspace_guard(work_order=None):
    if not user_has_mechanic_workspace_access(g.current_user):
        return api_response(False, error="Acesso restrito a manutencao.", status_code=403)
    if work_order and g.current_user.tipo == "mecanico" and work_order.assigned_mechanic_user_id != g.current_user.id:
        return api_response(False, error="Esta OS esta atribuida a outro mecanico.", status_code=403)


def _run(action, *, success_status=200):
    try:
        data = action()
        return api_response(True, data=data, status_code=success_status)
    except LookupError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/emergenciais")
@auth_required
def emergency_list():
    mechanic_id = g.current_user.id if g.current_user.tipo == "mecanico" else request.args.get("mecanico_id", type=int)
    return api_response(True, data=list_emergencies(status=request.args.get("status"), mechanic_id=mechanic_id))


@bp.post("/emergenciais")
@auth_required
def emergency_create():
    return _run(lambda: create_emergency(request.get_json(silent=True) or {}, g.current_user.id).to_dict(), success_status=201)


@bp.get("/emergenciais/<int:emergency_id>")
@auth_required
def emergency_detail(emergency_id):
    return _run(lambda: get_emergency(emergency_id).to_dict())


@bp.put("/emergenciais/<int:emergency_id>/triagem")
@auth_required
def emergency_triage(emergency_id):
    denied = _management_guard()
    if denied:
        return denied
    return _run(lambda: triage_emergency(emergency_id, request.get_json(silent=True) or {}, g.current_user.id).to_dict())


@bp.post("/emergenciais/<int:emergency_id>/converter-os")
@auth_required
def emergency_convert(emergency_id):
    denied = _management_guard()
    if denied:
        return denied
    return _run(lambda: convert_emergency_to_work_order(emergency_id, request.get_json(silent=True) or {}, g.current_user.id).to_dict(), success_status=201)


@bp.get("/ordens-servico/<int:work_order_id>")
@auth_required
def work_order_detail(work_order_id):
    try:
        order = get_work_order(work_order_id)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    denied = _workspace_guard(order)
    if denied:
        return denied
    data = order.to_dict()
    data["execution"] = order.execution.to_dict() if order.execution else None
    return api_response(True, data=data)


def _work_order_action(work_order_id, action):
    try:
        order = get_work_order(work_order_id)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    denied = _workspace_guard(order)
    if denied:
        return denied
    return _run(lambda: {**action(order.id).to_dict(), "execution": order.execution.to_dict()})


@bp.put("/ordens-servico/<int:work_order_id>/iniciar")
@auth_required
def work_order_start(work_order_id):
    return _work_order_action(work_order_id, lambda order_id: start_work_order(order_id, request.get_json(silent=True) or {}))


@bp.put("/ordens-servico/<int:work_order_id>/concluir-reparo")
@auth_required
def work_order_complete(work_order_id):
    return _work_order_action(work_order_id, lambda order_id: complete_repair(order_id, request.get_json(silent=True) or {}))


@bp.put("/ordens-servico/<int:work_order_id>/teste")
@auth_required
def work_order_test(work_order_id):
    return _work_order_action(work_order_id, lambda order_id: record_operational_test(order_id, request.get_json(silent=True) or {}))


@bp.put("/ordens-servico/<int:work_order_id>/liberar")
@auth_required
def work_order_release(work_order_id):
    return _work_order_action(work_order_id, lambda order_id: release_work_order(order_id, g.current_user.id))
