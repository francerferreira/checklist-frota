from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.models.equipment_structure import (
    EquipmentFamily,
    EquipmentLink,
    EquipmentLocationMovement,
    EquipmentProfile,
    OperationalLocation,
)
from app.models.operational_availability import EquipmentStatusEvent
from app.models.vehicle import Vehicle
from app.services.audit_service import record_event
from app.utils.timezone import MANAUS_TZ, now_manaus_naive


DEFAULT_EQUIPMENT_FAMILIES = (
    ("cavalo", "Cavalo", True),
    ("carreta", "Carreta", True),
    ("carro_simples", "Carro simples", True),
    ("cavalo_auxiliar", "Cavalo auxiliar", True),
    ("ambulancia", "Ambulancia", True),
    ("caminhao_pipa", "Caminhao pipa", True),
    ("caminhao_brigada", "Caminhao brigada", True),
    ("onibus", "Onibus", True),
    ("van", "Van", True),
    ("auxiliar", "Auxiliar legado", False),
    ("rtg", "RTG", False),
    ("lbs", "LBS", False),
    ("spreader", "Spreader", False),
)


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_id(value) -> int | None:
    if value in {None, ""}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Identificador invalido na estrutura do equipamento.") from exc
    return parsed if parsed > 0 else None


def _movement_datetime(value) -> datetime:
    if value in (None, ""):
        return now_manaus_naive()
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Data da movimentacao invalida.") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(MANAUS_TZ).replace(tzinfo=None)
    if parsed > now_manaus_naive():
        raise ValueError("Data da movimentacao nao pode estar no futuro.")
    return parsed


def _legacy_location_text(location: OperationalLocation) -> str:
    return location.full_name()[:120]


def seed_equipment_structure() -> None:
    families_by_code = {
        family.code: family for family in EquipmentFamily.query.order_by(EquipmentFamily.id.asc()).all()
    }
    for code, name, checklist_enabled in DEFAULT_EQUIPMENT_FAMILIES:
        family = families_by_code.get(code)
        if not family:
            family = EquipmentFamily(
                code=code,
                name=name,
                checklist_enabled=checklist_enabled,
                active=True,
            )
            db.session.add(family)
            families_by_code[code] = family
        elif code != "auxiliar":
            family.checklist_enabled = checklist_enabled
    db.session.flush()

    missing_profiles = (
        Vehicle.query.outerjoin(EquipmentProfile, EquipmentProfile.vehicle_id == Vehicle.id)
        .filter(EquipmentProfile.id.is_(None))
        .order_by(Vehicle.id.asc())
        .all()
    )
    for vehicle in missing_profiles:
        family = families_by_code.get(str(vehicle.tipo or "").strip().lower())
        if not family:
            continue
        db.session.add(
            EquipmentProfile(
                vehicle_id=vehicle.id,
                family_id=family.id,
                criticality="MEDIA",
            )
        )
    db.session.commit()


def resolve_equipment_family(payload: dict, vehicle_type: str | None) -> EquipmentFamily:
    family_id = _optional_id(payload.get("family_id")) if "family_id" in payload else None
    family_code = _clean(payload.get("family_code"))
    if family_id:
        family = db.session.get(EquipmentFamily, family_id)
    else:
        code = str(family_code or vehicle_type or "").strip().lower()
        family = EquipmentFamily.query.filter_by(code=code, active=True).first()
    if not family or not family.active:
        raise ValueError("Familia de equipamento invalida ou inativa.")
    return family


def apply_equipment_profile(vehicle: Vehicle, payload: dict) -> EquipmentProfile:
    family = resolve_equipment_family(payload, vehicle.tipo)
    vehicle.tipo = family.code

    profile = vehicle.equipment_profile
    if not profile:
        profile = EquipmentProfile(vehicle=vehicle, family_id=family.id)
        db.session.add(profile)
    profile.family_id = family.id

    if "operational_location_id" in payload:
        location_id = _optional_id(payload.get("operational_location_id"))
        location = db.session.get(OperationalLocation, location_id) if location_id else None
        if location_id and (not location or not location.active):
            raise ValueError("Local operacional invalido ou inativo.")
        profile.operational_location_id = location.id if location else None
        if location:
            vehicle.local = _legacy_location_text(location)

    if "serial_number" in payload:
        profile.serial_number = _clean(payload.get("serial_number"))
    if "manufacturer" in payload:
        profile.manufacturer = _clean(payload.get("manufacturer"))
    if "capacity" in payload:
        profile.capacity = _clean(payload.get("capacity"))
    if "criticality" in payload:
        criticality = str(payload.get("criticality") or "MEDIA").strip().upper()
        if criticality not in {"BAIXA", "MEDIA", "ALTA", "CRITICA"}:
            raise ValueError("Criticidade invalida.")
        profile.criticality = criticality
    return profile


def move_equipment_location(
    vehicle_id: int,
    payload: dict,
    *,
    user_id: int,
    source: str = "MANUAL",
) -> EquipmentLocationMovement:
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise LookupError("Equipamento ativo nao encontrado.")
    profile = (
        EquipmentProfile.query.filter_by(vehicle_id=vehicle.id)
        .with_for_update()
        .first()
    )
    if not profile:
        raise ValueError("Equipamento sem perfil tecnico para movimentacao.")

    destination_id = _optional_id(payload.get("to_location_id"))
    if not destination_id:
        raise ValueError("Informe o local de destino.")
    destination = db.session.get(OperationalLocation, destination_id)
    if not destination or not destination.active:
        raise ValueError("Local de destino invalido ou inativo.")

    origin = profile.location
    if origin and origin.id == destination.id:
        raise ValueError("O equipamento ja esta no local informado.")

    reason = _clean(payload.get("reason"))
    if not reason:
        raise ValueError("Informe o motivo da movimentacao.")
    if len(reason) > 255:
        raise ValueError("O motivo da movimentacao deve ter ate 255 caracteres.")

    moved_at = _movement_datetime(payload.get("moved_at"))
    latest = (
        EquipmentLocationMovement.query.filter_by(vehicle_id=vehicle.id)
        .order_by(
            EquipmentLocationMovement.moved_at.desc(),
            EquipmentLocationMovement.id.desc(),
        )
        .first()
    )
    if latest and moved_at <= latest.moved_at:
        raise ValueError("A movimentacao deve ser posterior ao ultimo registro do equipamento.")

    normalized_source = str(source or "MANUAL").strip().upper()
    if normalized_source not in {"MANUAL", "IMPORTADO", "AUTOMACAO", "MIGRACAO"}:
        raise ValueError("Origem da movimentacao invalida.")

    movement = EquipmentLocationMovement(
        vehicle_id=vehicle.id,
        from_location_id=origin.id if origin else None,
        to_location_id=destination.id,
        reason=reason,
        notes=_clean(payload.get("notes")),
        source=normalized_source,
        moved_at=moved_at,
        created_by_user_id=user_id,
    )
    db.session.add(movement)
    profile.operational_location_id = destination.id
    vehicle.local = _legacy_location_text(destination)
    db.session.flush()
    record_event(
        user_id=user_id,
        entity_type="EQUIPMENT_LOCATION_MOVEMENT",
        entity_id=movement.id,
        action="LOCATION_MOVED",
        old_value=origin.full_name() if origin else "SEM_LOCAL",
        new_value=f"{destination.full_name()} | Motivo: {reason}",
    )
    db.session.commit()
    return movement


def build_equipment_location_history(vehicle_id: int) -> dict:
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise LookupError("Equipamento nao encontrado.")
    profile = vehicle.equipment_profile
    movements = (
        EquipmentLocationMovement.query.filter_by(vehicle_id=vehicle.id)
        .order_by(
            EquipmentLocationMovement.moved_at.desc(),
            EquipmentLocationMovement.id.desc(),
        )
        .all()
    )
    return {
        "vehicle_id": vehicle.id,
        "current_location": profile.location.to_dict() if profile and profile.location else None,
        "movements": [movement.to_dict() for movement in movements],
    }


def _history_date(value, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} invalida.") from exc


def _link_at(links: list[EquipmentLink], event_at: datetime) -> EquipmentLink | None:
    matches = [
        link for link in links
        if link.started_at <= event_at and (link.ended_at is None or link.ended_at >= event_at)
    ]
    return max(matches, key=lambda link: link.started_at) if matches else None


def build_spreader_daily_history(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    spreader_id: int | None = None,
    lbs_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    start_date = _history_date(date_from, "Data inicial")
    end_date = _history_date(date_to, "Data final")
    if start_date and end_date and end_date < start_date:
        raise ValueError("A data final deve ser maior ou igual a data inicial.")

    query = (
        EquipmentStatusEvent.query
        .join(Vehicle, Vehicle.id == EquipmentStatusEvent.vehicle_id)
        .join(EquipmentProfile, EquipmentProfile.vehicle_id == Vehicle.id)
        .join(EquipmentFamily, EquipmentFamily.id == EquipmentProfile.family_id)
        .filter(EquipmentFamily.code == "spreader")
    )
    if spreader_id:
        query = query.filter(EquipmentStatusEvent.vehicle_id == spreader_id)
    if status:
        query = query.filter(EquipmentStatusEvent.status == status)
    if start_date:
        query = query.filter(EquipmentStatusEvent.started_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(EquipmentStatusEvent.started_at < datetime.combine(end_date + timedelta(days=1), time.min))
    events = query.order_by(EquipmentStatusEvent.started_at.desc(), EquipmentStatusEvent.id.desc()).all()
    if not events:
        return []

    spreader_ids = {event.vehicle_id for event in events}
    links = (
        EquipmentLink.query
        .filter(EquipmentLink.child_vehicle_id.in_(spreader_ids))
        .order_by(EquipmentLink.started_at.desc())
        .all()
    )
    links_by_spreader: dict[int, list[EquipmentLink]] = {}
    for link in links:
        links_by_spreader.setdefault(link.child_vehicle_id, []).append(link)

    rows = []
    for event in events:
        link = _link_at(links_by_spreader.get(event.vehicle_id, []), event.started_at)
        if lbs_id and (not link or link.parent_vehicle_id != lbs_id):
            continue
        spreader = event.vehicle
        spreader_profile = spreader.equipment_profile
        lbs = link.parent if link else None
        lbs_profile = lbs.equipment_profile if lbs else None
        location = lbs_profile.location if lbs_profile else None
        rows.append({
            "id": event.id,
            "started_at": event.started_at.isoformat() if event.started_at else None,
            "ended_at": event.ended_at.isoformat() if event.ended_at else None,
            "status": event.status,
            "reason": event.reason,
            "observation": event.observation,
            "evidence_path": event.evidence_path,
            "created_by": event.created_by.to_dict() if event.created_by else None,
            "spreader": {
                "id": spreader.id,
                "frota": spreader.frota,
                "serial_number": spreader_profile.serial_number if spreader_profile else None,
            },
            "lbs": {
                "id": lbs.id,
                "frota": lbs.frota,
                "location": location.full_name() if location else (lbs.local or None),
            } if lbs else None,
            "link_type": link.link_type if link else None,
        })
    return rows


def sync_active_equipment_link(
    child: Vehicle,
    payload: dict,
    *,
    user_id: int | None,
) -> EquipmentLink | None:
    if "parent_equipment_id" not in payload:
        return next((link for link in child.equipment_links_as_child if link.active), None)

    parent_id = _optional_id(payload.get("parent_equipment_id"))
    link_type = str(payload.get("link_type") or "ACOPLADO").strip().upper()
    if link_type not in {"TITULAR", "RESERVA", "ACOPLADO", "OUTRO"}:
        raise ValueError("Tipo de vinculo invalido.")

    active_links = EquipmentLink.query.filter_by(child_vehicle_id=child.id, active=True).all()
    if parent_id is None:
        for link in active_links:
            link.active = False
            link.ended_at = now_manaus_naive()
        return None

    parent = db.session.get(Vehicle, parent_id)
    if not parent or not parent.ativo:
        raise ValueError("Equipamento pai invalido ou inativo.")
    if parent.id == child.id:
        raise ValueError("Um equipamento nao pode ser vinculado a ele mesmo.")
    if child.tipo != "spreader" or parent.tipo != "lbs":
        raise ValueError("O vinculo titular/reserva deve ligar um Spreader a uma LBS.")

    current = next(
        (
            link
            for link in active_links
            if link.parent_vehicle_id == parent.id and link.link_type == link_type
        ),
        None,
    )
    if current:
        return current

    for link in active_links:
        link.active = False
        link.ended_at = now_manaus_naive()

    new_link = EquipmentLink(
        parent_vehicle_id=parent.id,
        child_vehicle_id=child.id,
        link_type=link_type,
        notes=_clean(payload.get("link_notes")),
        created_by_user_id=user_id,
    )
    db.session.add(new_link)
    return new_link
