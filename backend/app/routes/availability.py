from __future__ import annotations

from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.services.auth_service import auth_required
from app.services.availability_service import (
    build_availability_overview, list_hourmeter_readings, list_status_history,
    record_hourmeter, set_operational_status,
)
from app.utils.responses import api_response


bp = Blueprint("availability", __name__)


def _positive_int(value, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalido.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} invalido.")
    return parsed


@bp.get("/disponibilidade/visao")
@auth_required
def availability_overview():
    try:
        data = build_availability_overview(
            date_from=request.args.get("data_inicial"), date_to=request.args.get("data_final"),
            family_id=_positive_int(request.args.get("familia_id"), "Familia"),
            location_id=_positive_int(request.args.get("local_id"), "Local"),
        )
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=data)


@bp.put("/equipamentos/<int:vehicle_id>/status-operacional")
@auth_required
def update_operational_status(vehicle_id: int):
    try:
        data = set_operational_status(vehicle_id, request.get_json(silent=True) or {}, g.current_user.id)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=data)


@bp.get("/equipamentos/<int:vehicle_id>/status-historico")
@auth_required
def status_history(vehicle_id: int):
    try:
        return api_response(True, data=list_status_history(vehicle_id))
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)


@bp.post("/equipamentos/<int:vehicle_id>/horimetros")
@auth_required
def create_hourmeter_reading(vehicle_id: int):
    try:
        item = record_hourmeter(vehicle_id, request.get_json(silent=True) or {}, g.current_user.id)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Ja existe leitura neste mesmo instante.", status_code=409)
    return api_response(True, data=item.to_dict(), status_code=201)


@bp.get("/equipamentos/<int:vehicle_id>/horimetros")
@auth_required
def hourmeter_history(vehicle_id: int):
    try:
        return api_response(True, data=list_hourmeter_readings(vehicle_id))
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
