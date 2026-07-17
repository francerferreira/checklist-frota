from __future__ import annotations

from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import EquipmentFamily, EquipmentLink, OperationalLocation, Vehicle
from app.services.auth_service import auth_required, user_has_management_access
from app.services.equipment_structure_service import (
    build_equipment_location_history,
    move_equipment_location,
    sync_active_equipment_link,
)
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("equipment_structure", __name__)
LOCATION_TYPES = {"TERMINAL", "AREA", "PIER", "BERCO", "PATIO", "OUTRO"}


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return api_response(
            False,
            error="Somente admin ou gestor podem gerenciar a estrutura de equipamentos.",
            status_code=403,
        )
    return None


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integrity_error(error: IntegrityError):
    db.session.rollback()
    raw = str(getattr(error, "orig", error) or "").lower()
    if "serial_number" in raw:
        message = "Numero de serie ja cadastrado em outro equipamento."
    elif "code" in raw or "name" in raw:
        message = "Codigo ou nome ja cadastrado."
    else:
        message = "Registro duplicado ou vinculado a dados existentes."
    return api_response(False, error=message, status_code=409)


@bp.get("/equipamentos/estrutura")
@auth_required
def get_equipment_structure():
    families = EquipmentFamily.query.filter_by(active=True).order_by(EquipmentFamily.name.asc()).all()
    locations = OperationalLocation.query.filter_by(active=True).order_by(OperationalLocation.name.asc()).all()
    return api_response(
        True,
        data={
            "families": [family.to_dict() for family in families],
            "locations": [location.to_dict() for location in locations],
        },
    )


@bp.post("/equipamentos/familias")
@auth_required
def create_equipment_family():
    denied = _guard_management_access()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "").strip().lower()
    name = _clean(payload.get("name"))
    if not code or not name:
        return api_response(False, error="Informe codigo e nome da familia.", status_code=400)
    if len(code) > 20:
        return api_response(False, error="O codigo da familia deve ter ate 20 caracteres.", status_code=400)
    family = EquipmentFamily(
        code=code,
        name=name,
        description=_clean(payload.get("description")),
        checklist_enabled=bool(payload.get("checklist_enabled", False)),
        active=bool(payload.get("active", True)),
    )
    db.session.add(family)
    try:
        db.session.commit()
    except IntegrityError as exc:
        return _integrity_error(exc)
    return api_response(True, data=family.to_dict(), status_code=201)


@bp.put("/equipamentos/familias/<int:family_id>")
@auth_required
def update_equipment_family(family_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    family = EquipmentFamily.query.get_or_404(family_id)
    payload = request.get_json(silent=True) or {}
    if payload.get("name"):
        family.name = str(payload["name"]).strip()
    if "description" in payload:
        family.description = _clean(payload.get("description"))
    if "checklist_enabled" in payload:
        family.checklist_enabled = bool(payload.get("checklist_enabled"))
    if "active" in payload:
        family.active = bool(payload.get("active"))
    try:
        db.session.commit()
    except IntegrityError as exc:
        return _integrity_error(exc)
    return api_response(True, data=family.to_dict())


@bp.post("/equipamentos/locais")
@auth_required
def create_operational_location():
    denied = _guard_management_access()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "").strip().upper()
    name = _clean(payload.get("name"))
    location_type = str(payload.get("location_type") or "OUTRO").strip().upper()
    if not code or not name:
        return api_response(False, error="Informe codigo e nome do local.", status_code=400)
    if location_type not in LOCATION_TYPES:
        return api_response(False, error="Tipo de local invalido.", status_code=400)
    parent_id = payload.get("parent_id") or None
    try:
        parent_id = int(parent_id) if parent_id else None
    except (TypeError, ValueError):
        return api_response(False, error="Local superior invalido.", status_code=400)
    if parent_id and not db.session.get(OperationalLocation, parent_id):
        return api_response(False, error="Local superior nao encontrado.", status_code=400)
    location = OperationalLocation(
        code=code,
        name=name,
        location_type=location_type,
        parent_id=parent_id,
        active=bool(payload.get("active", True)),
    )
    db.session.add(location)
    try:
        db.session.commit()
    except IntegrityError as exc:
        return _integrity_error(exc)
    return api_response(True, data=location.to_dict(), status_code=201)


@bp.put("/equipamentos/locais/<int:location_id>")
@auth_required
def update_operational_location(location_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    location = OperationalLocation.query.get_or_404(location_id)
    payload = request.get_json(silent=True) or {}
    if payload.get("name"):
        location.name = str(payload["name"]).strip()
    if payload.get("location_type"):
        location_type = str(payload["location_type"]).strip().upper()
        if location_type not in LOCATION_TYPES:
            return api_response(False, error="Tipo de local invalido.", status_code=400)
        location.location_type = location_type
    if "parent_id" in payload:
        parent_id = payload.get("parent_id") or None
        try:
            parent_id = int(parent_id) if parent_id else None
        except (TypeError, ValueError):
            return api_response(False, error="Local superior invalido.", status_code=400)
        if parent_id and parent_id == location.id:
            return api_response(False, error="Um local nao pode ser superior de si mesmo.", status_code=400)
        if parent_id and not db.session.get(OperationalLocation, parent_id):
            return api_response(False, error="Local superior nao encontrado.", status_code=400)
        location.parent_id = parent_id
    if "active" in payload:
        location.active = bool(payload.get("active"))
    try:
        db.session.commit()
    except IntegrityError as exc:
        return _integrity_error(exc)
    return api_response(True, data=location.to_dict())


@bp.get("/equipamentos/<int:vehicle_id>/movimentos-localizacao")
@auth_required
def equipment_location_history(vehicle_id: int):
    try:
        data = build_equipment_location_history(vehicle_id)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    return api_response(True, data=data)


@bp.post("/equipamentos/<int:vehicle_id>/movimentos-localizacao")
@auth_required
def create_equipment_location_movement(vehicle_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        movement = move_equipment_location(
            vehicle_id,
            request.get_json(silent=True) or {},
            user_id=g.current_user.id,
        )
    except LookupError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError as exc:
        return _integrity_error(exc)
    return api_response(True, data=movement.to_dict(), status_code=201)


@bp.get("/equipamentos/vinculos")
@auth_required
def list_equipment_links():
    query = EquipmentLink.query.order_by(EquipmentLink.started_at.desc())
    if request.args.get("active") == "true":
        query = query.filter_by(active=True)
    if request.args.get("parent_equipment_id"):
        query = query.filter_by(parent_vehicle_id=int(request.args["parent_equipment_id"]))
    if request.args.get("child_equipment_id"):
        query = query.filter_by(child_vehicle_id=int(request.args["child_equipment_id"]))
    return api_response(True, data=[link.to_dict() for link in query.all()])


@bp.post("/equipamentos/vinculos")
@auth_required
def create_equipment_link():
    denied = _guard_management_access()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    child_id = payload.get("child_equipment_id")
    if not child_id:
        return api_response(False, error="Informe o Spreader do vinculo.", status_code=400)
    child = db.session.get(Vehicle, int(child_id))
    if not child:
        return api_response(False, error="Spreader nao encontrado.", status_code=404)
    try:
        link = sync_active_equipment_link(child, payload, user_id=g.current_user.id)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=link.to_dict() if link else None, status_code=201)


@bp.put("/equipamentos/vinculos/<int:link_id>/encerrar")
@auth_required
def close_equipment_link(link_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    link = EquipmentLink.query.get_or_404(link_id)
    link.active = False
    link.ended_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data=link.to_dict())
