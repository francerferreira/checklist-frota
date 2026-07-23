from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, g, request

from app.extensions import db
from app.models import MaintenanceResource, MaintenanceResourceReservation, MaintenanceWorkOrder
from app.services.auth_service import auth_required, user_has_management_access
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("resources", __name__)

RESOURCE_TYPES = {"FERRAMENTA", "INSTRUMENTO", "EQUIPAMENTO"}


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar recursos.", status_code=403)
    return None


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_date(value, field: str, *, required: bool = False) -> date | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"Informe {field}.")
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalida.") from exc


def _parse_datetime(value, field: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value or ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Informe {field} no formato data e hora ISO.") from exc


def _resource_payload(payload: dict) -> dict:
    code = _clean(payload.get("code"))
    name = _clean(payload.get("name"))
    resource_type = str(payload.get("resource_type") or "").strip().upper()
    if not code or not name:
        raise ValueError("Informe codigo e nome do recurso.")
    if resource_type not in RESOURCE_TYPES:
        raise ValueError("Tipo de recurso invalido.")
    calibration_required = bool(payload.get("calibration_required"))
    calibration_due_date = _parse_date(
        payload.get("calibration_due_date"),
        "a data de calibracao",
        required=calibration_required,
    )
    return {
        "code": code.upper(),
        "name": name,
        "resource_type": resource_type,
        "active": bool(payload.get("active", True)),
        "calibration_required": calibration_required,
        "calibration_due_date": calibration_due_date,
        "notes": _clean(payload.get("notes")),
    }


def _run(action, *, status_code: int = 200):
    try:
        return api_response(True, data=action(), status_code=status_code)
    except LookupError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/recursos")
@auth_required
def list_resources():
    denied = _guard_management()
    if denied:
        return denied
    rows = MaintenanceResource.query.order_by(MaintenanceResource.active.desc(), MaintenanceResource.name.asc()).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.post("/recursos")
@auth_required
def create_resource():
    denied = _guard_management()
    if denied:
        return denied

    def action():
        data = _resource_payload(request.get_json(silent=True) or {})
        if MaintenanceResource.query.filter_by(code=data["code"]).first():
            raise ValueError("Ja existe um recurso com este codigo.")
        resource = MaintenanceResource(**data)
        db.session.add(resource)
        db.session.commit()
        return resource.to_dict()

    return _run(action, status_code=201)


@bp.get("/recursos/<int:resource_id>/reservas")
@auth_required
def list_resource_reservations(resource_id: int):
    denied = _guard_management()
    if denied:
        return denied
    resource = db.session.get(MaintenanceResource, resource_id)
    if not resource:
        return api_response(False, error="Recurso nao encontrado.", status_code=404)
    rows = (
        MaintenanceResourceReservation.query
        .filter_by(resource_id=resource_id)
        .order_by(MaintenanceResourceReservation.starts_at.desc())
        .all()
    )
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.post("/recursos/<int:resource_id>/reservas")
@auth_required
def reserve_resource(resource_id: int):
    denied = _guard_management()
    if denied:
        return denied

    def action():
        resource = db.session.get(MaintenanceResource, resource_id)
        if not resource:
            raise LookupError("Recurso nao encontrado.")
        if not resource.active:
            raise ValueError("Recurso inativo nao pode ser reservado.")
        if resource.calibration_status() == "VENCIDA":
            raise ValueError("Recurso com calibracao vencida nao pode ser reservado.")
        payload = request.get_json(silent=True) or {}
        starts_at = _parse_datetime(payload.get("starts_at"), "o inicio da reserva")
        ends_at = _parse_datetime(payload.get("ends_at"), "o fim da reserva")
        if ends_at <= starts_at:
            raise ValueError("O fim da reserva deve ser posterior ao inicio.")
        work_order_id = payload.get("work_order_id")
        if work_order_id not in (None, ""):
            try:
                work_order_id = int(work_order_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("OS invalida.") from exc
            if not db.session.get(MaintenanceWorkOrder, work_order_id):
                raise ValueError("OS nao encontrada.")
        else:
            work_order_id = None
        conflict = MaintenanceResourceReservation.query.filter(
            MaintenanceResourceReservation.resource_id == resource.id,
            MaintenanceResourceReservation.status == "RESERVADA",
            MaintenanceResourceReservation.starts_at < ends_at,
            MaintenanceResourceReservation.ends_at > starts_at,
        ).first()
        if conflict:
            raise ValueError("Recurso ja possui reserva no periodo informado.")
        reservation = MaintenanceResourceReservation(
            resource_id=resource.id,
            work_order_id=work_order_id,
            starts_at=starts_at,
            ends_at=ends_at,
            notes=_clean(payload.get("notes")),
            created_by_user_id=g.current_user.id,
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation.to_dict()

    return _run(action, status_code=201)


@bp.post("/recursos/reservas/<int:reservation_id>/cancelar")
@auth_required
def cancel_resource_reservation(reservation_id: int):
    denied = _guard_management()
    if denied:
        return denied

    def action():
        reservation = db.session.get(MaintenanceResourceReservation, reservation_id)
        if not reservation:
            raise LookupError("Reserva nao encontrada.")
        if reservation.status == "CANCELADA":
            raise ValueError("Reserva ja esta cancelada.")
        reservation.status = "CANCELADA"
        reservation.cancellation_reason = _clean((request.get_json(silent=True) or {}).get("reason"))
        reservation.cancelled_at = now_manaus_naive()
        db.session.commit()
        return reservation.to_dict()

    return _run(action)
