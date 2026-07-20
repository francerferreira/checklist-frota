from flask import Blueprint, g, request

from app.services.auth_service import auth_required, user_has_management_access
from app.services.maintenance_dashboard_service import (
    build_dashboard_availability,
    build_dashboard_critical_equipment,
    build_dashboard_filter_options,
    build_dashboard_preventives,
    build_dashboard_summary,
    build_dashboard_work_orders,
    parse_dashboard_filters,
)
from app.utils.responses import api_response


bp = Blueprint("maintenance_dashboard", __name__, url_prefix="/dashboard-manutencao")


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem visualizar o dashboard de manutencao.", status_code=403)
    return None


def _run(action):
    denied = _guard_management()
    if denied:
        return denied
    try:
        return api_response(True, data=action())
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/filtros")
@auth_required
def filters():
    return _run(build_dashboard_filter_options)


@bp.get("/resumo")
@auth_required
def summary():
    return _run(lambda: build_dashboard_summary(parse_dashboard_filters(request.args)))


@bp.get("/disponibilidade")
@auth_required
def availability():
    return _run(lambda: build_dashboard_availability(parse_dashboard_filters(request.args)))


@bp.get("/ordens")
@auth_required
def work_orders():
    return _run(
        lambda: build_dashboard_work_orders(
            parse_dashboard_filters(request.args),
            page=request.args.get("pagina", default=1, type=int),
            page_size=request.args.get("tamanho_pagina", default=50, type=int),
        )
    )


@bp.get("/preventivas")
@auth_required
def preventives():
    return _run(lambda: build_dashboard_preventives(parse_dashboard_filters(request.args)))


@bp.get("/ativos-criticos")
@auth_required
def critical_equipment():
    return _run(lambda: build_dashboard_critical_equipment(parse_dashboard_filters(request.args)))
