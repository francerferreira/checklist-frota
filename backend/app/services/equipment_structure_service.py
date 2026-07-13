from __future__ import annotations

from app.extensions import db
from app.models.equipment_structure import (
    EquipmentFamily,
    EquipmentLink,
    EquipmentProfile,
    OperationalLocation,
)
from app.models.vehicle import Vehicle
from app.utils.timezone import now_manaus_naive


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
            vehicle.local = location.full_name()

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
