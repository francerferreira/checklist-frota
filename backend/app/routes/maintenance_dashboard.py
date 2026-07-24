from flask import Blueprint, g, request

from app.extensions import db
from app.services.audit_service import record_event
from app.services.auth_service import auth_required, user_has_management_access
from app.services.dashboard_tv_access_service import (
    build_tv_dashboard_payload,
    create_tv_access_token,
    list_tv_access_tokens,
    revoke_tv_access_token,
)
from app.services.maintenance_dashboard_service import (
    build_dashboard_availability,
    build_dashboard_charts,
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


@bp.get("/graficos")
@auth_required
def charts():
    return _run(lambda: build_dashboard_charts(parse_dashboard_filters(request.args)))


@bp.get("/tv/dados")
def tv_data():
    try:
        return api_response(True, data=build_tv_dashboard_payload(parse_dashboard_filters(request.args)))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/tv/acessos")
@auth_required
def tv_accesses():
    return _run(lambda: {"items": list_tv_access_tokens()})


@bp.post("/tv/acessos")
@auth_required
def create_tv_access():
    denied = _guard_management()
    if denied:
        return denied
    try:
        access, raw_token = create_tv_access_token(g.current_user, request.get_json(silent=True) or {})
        record_event(
            user_id=g.current_user.id,
            entity_type="DASHBOARD_TV_ACCESS",
            entity_id=access.id,
            action="TV_ACCESS_CREATED",
            new_value=f"name={access.name}; expires_at={access.expires_at.isoformat()}",
        )
        db.session.commit()
        return api_response(True, data={"access": access.to_dict(), "token": raw_token}, status_code=201)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.delete("/tv/acessos/<int:access_id>")
@auth_required
def revoke_tv_access(access_id: int):
    denied = _guard_management()
    if denied:
        return denied
    try:
        access = revoke_tv_access_token(access_id)
        record_event(
            user_id=g.current_user.id,
            entity_type="DASHBOARD_TV_ACCESS",
            entity_id=access.id,
            action="TV_ACCESS_REVOKED",
            new_value=f"name={access.name}; revoked_at={access.revoked_at.isoformat() if access.revoked_at else '-'}",
        )
        db.session.commit()
        return api_response(True, data=access.to_dict())
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=404)


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
