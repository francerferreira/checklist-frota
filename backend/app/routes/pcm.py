from datetime import date, timedelta

from flask import Blueprint, g, request

from app.extensions import db
from app.services.auth_service import auth_required, user_has_management_access
from app.services.pcm_service import (
    build_backlog,
    build_pcm_agenda,
    build_pcm_programming_window,
    create_preventive_plan,
    generate_due_preventives,
    get_preventive_plan,
    list_preventive_plans,
    update_preventive_plan,
)
from app.services.preventive_service import (
    create_preventive_execution,
    get_preventive_execution,
    integrate_preventive_execution,
    list_preventive_executions,
    update_preventive_execution,
    update_preventive_stage,
)
from app.utils.responses import api_response


bp = Blueprint("pcm", __name__)


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar o PCM.", status_code=403)


def _run(action, *, status_code=200):
    try:
        return api_response(True, data=action(), status_code=status_code)
    except LookupError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/pcm/agenda")
@auth_required
def pcm_agenda():
    denied = _guard_management()
    if denied:
        return denied
    return _run(lambda: build_pcm_agenda(request.args.get("ano", type=int), request.args.get("mes", type=int)))


@bp.get("/pcm/backlog")
@auth_required
def pcm_backlog():
    denied = _guard_management()
    if denied:
        return denied
    return api_response(True, data=build_backlog())


@bp.get("/pcm/programacao")
@auth_required
def pcm_programming():
    denied = _guard_management()
    if denied:
        return denied
    today = date.today()
    try:
        start = date.fromisoformat(str(request.args.get("data_inicial") or today.isoformat()))
        end = date.fromisoformat(str(request.args.get("data_final") or (today + timedelta(days=14)).isoformat()))
        capacity = request.args.get("capacidade_minutos", default=480, type=int)
        if capacity is None:
            raise ValueError("Capacidade diaria invalida.")
        return api_response(True, data=build_pcm_programming_window(start_date=start, end_date=end, daily_capacity_minutes=capacity))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/pcm/planos-preventivos")
@auth_required
def preventive_plan_list():
    denied = _guard_management()
    if denied:
        return denied
    return api_response(True, data=list_preventive_plans())


@bp.get("/pcm/planos-preventivos/<int:plan_id>")
@auth_required
def preventive_plan_detail(plan_id: int):
    denied = _guard_management()
    if denied:
        return denied
    return _run(lambda: get_preventive_plan(plan_id).to_dict())


@bp.post("/pcm/planos-preventivos")
@auth_required
def preventive_plan_create():
    denied = _guard_management()
    if denied:
        return denied
    return _run(lambda: create_preventive_plan(request.get_json(silent=True) or {}, g.current_user.id).to_dict(), status_code=201)


@bp.put("/pcm/planos-preventivos/<int:plan_id>")
@auth_required
def preventive_plan_update(plan_id: int):
    denied = _guard_management()
    if denied:
        return denied
    return _run(lambda: update_preventive_plan(plan_id, request.get_json(silent=True) or {}).to_dict())


@bp.post("/pcm/gerar-preventivas")
@auth_required
def preventive_generation():
    denied = _guard_management()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    return _run(lambda: generate_due_preventives(g.current_user.id, payload.get("plan_id")))


@bp.get("/pcm/preventivas/execucoes")
@auth_required
def preventive_execution_list():
    denied = _guard_management()
    if denied:
        return denied
    return _run(
        lambda: list_preventive_executions(
            vehicle_id=request.args.get("vehicle_id", type=int),
            plan_id=request.args.get("plan_id", type=int),
            status=request.args.get("status"),
        )
    )


@bp.get("/pcm/preventivas/execucoes/<int:execution_id>")
@auth_required
def preventive_execution_detail(execution_id: int):
    denied = _guard_management()
    if denied:
        return denied
    return _run(lambda: get_preventive_execution(execution_id).to_dict())


@bp.post("/pcm/preventivas/execucoes")
@auth_required
def preventive_execution_create():
    denied = _guard_management()
    if denied:
        return denied
    return _run(
        lambda: create_preventive_execution(request.get_json(silent=True) or {}, g.current_user.id).to_dict(),
        status_code=201,
    )


@bp.put("/pcm/preventivas/execucoes/<int:execution_id>")
@auth_required
def preventive_execution_update(execution_id: int):
    denied = _guard_management()
    if denied:
        return denied
    return _run(
        lambda: update_preventive_execution(execution_id, request.get_json(silent=True) or {}, g.current_user.id).to_dict()
    )


@bp.post("/pcm/preventivas/execucoes/<int:execution_id>/integrar")
@auth_required
def preventive_execution_integrate(execution_id: int):
    denied = _guard_management()
    if denied:
        return denied
    return _run(lambda: integrate_preventive_execution(execution_id, request.get_json(silent=True) or {}, g.current_user.id))


@bp.put("/pcm/preventivas/execucoes/<int:execution_id>/etapas/<int:stage_id>")
@auth_required
def preventive_stage_update(execution_id: int, stage_id: int):
    denied = _guard_management()
    if denied:
        return denied
    def action():
        execution = get_preventive_execution(execution_id)
        if not any(stage.id == stage_id for stage in execution.stages):
            raise ValueError("A etapa nao pertence a esta execucao preventiva.")
        return update_preventive_stage(stage_id, request.get_json(silent=True) or {}, g.current_user.id).to_dict()

    return _run(action)
