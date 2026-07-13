from __future__ import annotations

from flask import Blueprint, g, request

from app.extensions import db
from app.services.auth_service import auth_required, user_has_management_access
from app.services.technical_inspection_service import (
    create_execution, create_new_version, create_template, list_executions,
    list_templates, publish_template, update_template,
)
from app.utils.responses import api_response


bp = Blueprint("technical_inspections", __name__)


def _management_guard():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar templates tecnicos.", status_code=403)
    return None


def _run(action, *, created=False):
    try:
        data = action()
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    if hasattr(data, "to_dict"):
        data = data.to_dict()
    return api_response(True, data=data, status_code=201 if created else 200)


@bp.get("/inspecoes-tecnicas/modelos")
@auth_required
def templates():
    include_all = request.args.get("incluir_todos") == "true"
    if include_all:
        denied = _management_guard()
        if denied:
            return denied
    vehicle_id = request.args.get("vehicle_id", type=int)
    return _run(lambda: list_templates(include_all=include_all, vehicle_id=vehicle_id))


@bp.post("/inspecoes-tecnicas/modelos")
@auth_required
def add_template():
    denied = _management_guard()
    if denied:
        return denied
    return _run(lambda: create_template(request.get_json(silent=True) or {}, g.current_user.id), created=True)


@bp.put("/inspecoes-tecnicas/modelos/<int:template_id>")
@auth_required
def edit_template(template_id: int):
    denied = _management_guard()
    if denied:
        return denied
    return _run(lambda: update_template(template_id, request.get_json(silent=True) or {}))


@bp.post("/inspecoes-tecnicas/modelos/<int:template_id>/publicar")
@auth_required
def publish(template_id: int):
    denied = _management_guard()
    if denied:
        return denied
    return _run(lambda: publish_template(template_id))


@bp.post("/inspecoes-tecnicas/modelos/<int:template_id>/nova-versao")
@auth_required
def new_version(template_id: int):
    denied = _management_guard()
    if denied:
        return denied
    return _run(lambda: create_new_version(template_id, g.current_user.id), created=True)


@bp.post("/inspecoes-tecnicas/execucoes")
@auth_required
def add_execution():
    return _run(lambda: create_execution(request.get_json(silent=True) or {}, g.current_user.id), created=True)


@bp.get("/inspecoes-tecnicas/execucoes")
@auth_required
def executions():
    return _run(lambda: list_executions(
        vehicle_id=request.args.get("vehicle_id", type=int),
        limit=request.args.get("limit", default=100, type=int),
    ))
