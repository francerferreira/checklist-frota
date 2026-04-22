from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import Activity, ActivityItem, ActivityNonConformityLink, Checklist, ChecklistItem, Vehicle


def normalize_item_key(item_name: str | None) -> str:
    return " ".join(str(item_name or "").strip().upper().split())


def normalize_modulo(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"cavalo", "carreta", "outros"}:
        return normalized
    return "all"


def match_modulo(vehicle_type: str | None, modulo: str | None) -> bool:
    modulo_norm = normalize_modulo(modulo)
    vehicle_norm = (vehicle_type or "").strip().lower()
    if modulo_norm == "all":
        return True
    if modulo_norm in {"cavalo", "carreta"}:
        return vehicle_norm == modulo_norm
    return vehicle_norm not in {"cavalo", "carreta"}


def get_non_conformities_for_mass_activity(
    *,
    item_name: str,
    modulo: str | None = None,
    status_nc: str | None = "abertas",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[ChecklistItem]:
    source_key = normalize_item_key(item_name)
    if not source_key:
        return []

    query = (
        ChecklistItem.query.join(Checklist).join(Vehicle).filter(ChecklistItem.status == "NC")
        .filter(func.upper(func.trim(ChecklistItem.item_nome)) == source_key)
        .order_by(ChecklistItem.created_at.desc())
    )

    status_norm = (status_nc or "").strip().lower()
    if status_norm == "abertas":
        query = query.filter(ChecklistItem.resolvido.is_(False))
    elif status_norm == "resolvidas":
        query = query.filter(ChecklistItem.resolvido.is_(True))

    modulo_norm = normalize_modulo(modulo)
    if modulo_norm == "cavalo":
        query = query.filter(Vehicle.tipo == "cavalo")
    elif modulo_norm == "carreta":
        query = query.filter(Vehicle.tipo == "carreta")
    elif modulo_norm == "outros":
        query = query.filter(func.coalesce(Vehicle.tipo, "").notin_(["cavalo", "carreta"]))

    if date_from:
        query = query.filter(ChecklistItem.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        end = datetime.fromisoformat(date_to) + timedelta(days=1)
        query = query.filter(ChecklistItem.created_at < end)
    return query.all()


def ensure_activity_item(activity: Activity, vehicle_id: int) -> ActivityItem:
    item = ActivityItem.query.filter_by(activity_id=activity.id, vehicle_id=vehicle_id).first()
    if item:
        return item
    item = ActivityItem(
        activity_id=activity.id,
        vehicle_id=vehicle_id,
        material_id=activity.material_id,
        quantidade_peca=max(1, int(activity.quantidade_por_equipamento or 1)),
        codigo_peca=activity.codigo_peca,
        descricao_peca=activity.descricao_peca,
        status_execucao="PENDENTE",
    )
    db.session.add(item)
    db.session.flush()
    return item


def link_non_conformity_to_activity(activity: Activity, checklist_item: ChecklistItem, *, mode: str = "MANUAL") -> bool:
    if checklist_item.status != "NC":
        return False

    existing = ActivityNonConformityLink.query.filter_by(checklist_item_id=checklist_item.id).first()
    if existing:
        return False

    vehicle = checklist_item.checklist.vehicle if checklist_item.checklist else None
    if not vehicle:
        return False

    activity_item = ensure_activity_item(activity, vehicle.id)
    link = ActivityNonConformityLink(
        activity_id=activity.id,
        activity_item_id=activity_item.id,
        checklist_item_id=checklist_item.id,
        linked_by_mode="AUTO" if str(mode).strip().upper() == "AUTO" else "MANUAL",
    )
    db.session.add(link)
    return True


def auto_link_non_conformities_to_open_activities(items: list[ChecklistItem] | None) -> int:
    if not items:
        return 0

    linked = 0
    for checklist_item in items:
        if checklist_item.status != "NC":
            continue

        source_key = normalize_item_key(checklist_item.item_nome)
        if not source_key:
            continue

        vehicle = checklist_item.checklist.vehicle if checklist_item.checklist else None
        vehicle_type = vehicle.tipo if vehicle else None
        candidates = (
            Activity.query.filter_by(status="ABERTA", source_type="NC_ITEM", source_key=source_key, auto_link_nc=True)
            .order_by(Activity.created_at.desc())
            .all()
        )

        vehicle_modulo = normalize_modulo(vehicle_type)
        if vehicle_modulo == "all":
            vehicle_modulo = "outros"

        matched_activity = next(
            (
                activity
                for activity in candidates
                if normalize_modulo(activity.source_modulo) == vehicle_modulo and match_modulo(vehicle_type, activity.source_modulo)
            ),
            None,
        )
        if not matched_activity:
            matched_activity = next(
                (
                    activity
                    for activity in candidates
                    if normalize_modulo(activity.source_modulo) == "all" and match_modulo(vehicle_type, activity.source_modulo)
                ),
                None,
            )

        if not matched_activity:
            continue

        if link_non_conformity_to_activity(matched_activity, checklist_item, mode="AUTO"):
            linked += 1

    if linked:
        db.session.commit()
    return linked
