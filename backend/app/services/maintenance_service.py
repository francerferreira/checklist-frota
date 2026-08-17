from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import lazyload

from app.extensions import db
from app.utils.timezone import now_manaus_naive, today_manaus
from app.models import (
    Activity,
    ChecklistItem,
    Material,
    MaintenanceMaterial,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    ResolutionPackage,
    WashQueueItem,
)
from app.models.maintenance import PACKAGE_SOURCE_PREFIX, PLANNED_CORRECTIVE_SOURCE_PREFIX
from app.services.audit_service import record_event
from app.services.material_service import register_material_movement


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_type(value: str | None) -> str:
    normalized = (_clean(value) or "CHECKLIST_NC").upper()
    if normalized == "PACOTE_RESOLUCAO":
        return normalized
    if normalized not in {"CHECKLIST_NC", "ATIVIDADE", "PREVENTIVA", "CORRETIVA_PROGRAMADA"}:
        raise ValueError("Tipo de manutenção inválido.")
    return normalized


def _normalize_status(value: str | None, default: str = "ABERTA") -> str:
    normalized = (_clean(value) or default).upper()
    allowed = {"ABERTA", "AGUARDANDO_MATERIAL", "PROGRAMADA", "EM_EXECUCAO", "CONCLUIDA", "CANCELADA"}
    if normalized not in allowed:
        raise ValueError("Status de programação inválido.")
    return normalized


def _normalize_item_status(value: str | None, default: str = "PENDENTE") -> str:
    normalized = (_clean(value) or default).upper()
    allowed = {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "INSTALADO", "NAO_EXECUTADO", "REPROGRAMADO", "CANCELADO"}
    if normalized not in allowed:
        raise ValueError("Status do item inválido.")
    return normalized


def _normalize_material_status(value: str | None, default: str = "AGUARDANDO_MATERIAL") -> str:
    normalized = (_clean(value) or default).upper()
    allowed = {"AGUARDANDO_MATERIAL", "EM_COMPRAS", "DISPONIVEL_EM_ESTOQUE", "RESERVADO", "UTILIZADO"}
    if normalized not in allowed:
        raise ValueError("Status do material inválido.")
    return normalized


def _parse_date(value: str | date | datetime | None, *, default: date | None = None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if not text:
        return default
    return datetime.fromisoformat(text).date()


def _normalize_daily_capacity(value, *, default: int = 1) -> int:
    try:
        capacity = int(value or default)
    except (TypeError, ValueError):
        raise ValueError("A capacidade diária deve ser maior que zero.")
    if capacity <= 0:
        raise ValueError("A capacidade diária deve ser maior que zero.")
    return capacity


def _parse_int(value, default: int | None = None) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_item_key_from_text(value: str | None) -> str:
    return (_clean(value) or "").strip().upper()


def _month_label(year: int, month: int) -> str:
    labels = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]
    return f"{labels[month - 1]} de {year}"


def _schedule_source_origin_type(schedule: MaintenanceSchedule | None) -> str:
    if not schedule:
        return "-"
    source_key = str(schedule.source_key or "")
    if source_key.startswith(PACKAGE_SOURCE_PREFIX):
        return "PACOTE_RESOLUCAO"
    if source_key.startswith(PLANNED_CORRECTIVE_SOURCE_PREFIX):
        return "CORRETIVA_PROGRAMADA"
    return str(schedule.source_type or "-").upper()


def _effective_item_name_for_history(item: MaintenanceScheduleItem) -> str:
    if item.checklist_item:
        return _normalize_item_key_from_text(item.checklist_item.item_principal or item.checklist_item.item_nome)
    if item.activity:
        return _normalize_item_key_from_text(item.activity.item_nome or item.activity.titulo)
    if item.schedule:
        return _normalize_item_key_from_text(item.schedule.item_name or item.schedule.title)
    return ""


def _extract_suggestion_targets(payload: dict) -> tuple[set[str], set[int]]:
    source_type = _normalize_type(payload.get("source_type") or payload.get("tipo") or payload.get("origem"))
    item_names: set[str] = set()
    vehicle_ids: set[int] = set()

    package_ids = [int(value) for value in payload.get("package_ids") or []]
    activity_ids = [int(value) for value in payload.get("activity_ids") or []]
    checklist_item_ids = [int(value) for value in payload.get("checklist_item_ids") or []]
    payload_vehicle_ids = [int(value) for value in payload.get("vehicle_ids") or []]

    if source_type == "PACOTE_RESOLUCAO" and package_ids:
        packages = ResolutionPackage.query.filter(ResolutionPackage.id.in_(package_ids)).all()
        for package in packages:
            if package.item_name:
                item_names.add(_normalize_item_key_from_text(package.item_name))
            for link in package.links:
                checklist_item = link.checklist_item
                if not checklist_item:
                    continue
                item_names.add(_normalize_item_key_from_text(checklist_item.item_principal or checklist_item.item_nome))
                if checklist_item.checklist and checklist_item.checklist.vehicle_id:
                    vehicle_ids.add(int(checklist_item.checklist.vehicle_id))
    elif source_type == "ATIVIDADE" and activity_ids:
        activities = Activity.query.filter(Activity.id.in_(activity_ids)).all()
        for activity in activities:
            item_names.add(_normalize_item_key_from_text(activity.item_nome or activity.titulo))
            for activity_item in activity.items:
                if activity_item.vehicle_id:
                    vehicle_ids.add(int(activity_item.vehicle_id))
    elif checklist_item_ids:
        checklist_items = ChecklistItem.query.filter(ChecklistItem.id.in_(checklist_item_ids)).all()
        for checklist_item in checklist_items:
            item_names.add(_normalize_item_key_from_text(checklist_item.item_principal or checklist_item.item_nome))
            if checklist_item.checklist and checklist_item.checklist.vehicle_id:
                vehicle_ids.add(int(checklist_item.checklist.vehicle_id))
    else:
        for vehicle_id in payload_vehicle_ids:
            vehicle_ids.add(int(vehicle_id))
        fallback_item = _normalize_item_key_from_text(payload.get("item_name") or payload.get("item_nome"))
        if fallback_item:
            item_names.add(fallback_item)

    item_names.discard("")
    return item_names, vehicle_ids


def suggest_mechanic_for_payload(payload: dict) -> dict | None:
    target_item_names, target_vehicle_ids = _extract_suggestion_targets(payload)
    history_rows = MaintenanceScheduleItem.query.order_by(
        MaintenanceScheduleItem.executed_at.desc().nullslast(),
        MaintenanceScheduleItem.updated_at.desc(),
    ).all()

    scores: dict[int, dict] = {}
    for row in history_rows:
        mechanic = row.assigned_mechanic or (row.schedule.assigned_mechanic if row.schedule else None)
        mechanic_id = row.assigned_mechanic_user_id or (row.schedule.assigned_mechanic_user_id if row.schedule else None)
        if not mechanic_id or not mechanic:
            continue

        score = 0
        row_item_name = _effective_item_name_for_history(row)
        if row_item_name and row_item_name in target_item_names:
            score += 5
        if row.vehicle_id and int(row.vehicle_id) in target_vehicle_ids:
            score += 2
        if row.status == "INSTALADO":
            score += 1
        if score <= 0:
            continue

        entry = scores.setdefault(
            int(mechanic_id),
            {
                "user_id": int(mechanic_id),
                "user": mechanic.to_dict(),
                "score": 0,
                "item_matches": 0,
                "vehicle_matches": 0,
                "resolved_matches": 0,
            },
        )
        entry["score"] += score
        if row_item_name and row_item_name in target_item_names:
            entry["item_matches"] += 1
        if row.vehicle_id and int(row.vehicle_id) in target_vehicle_ids:
            entry["vehicle_matches"] += 1
        if row.status == "INSTALADO":
            entry["resolved_matches"] += 1

    if not scores:
        return None

    best = max(
        scores.values(),
        key=lambda row: (row["score"], row["item_matches"], row["resolved_matches"], row["vehicle_matches"], -row["user_id"]),
    )
    reason_parts: list[str] = []
    if best["item_matches"]:
        reason_parts.append(f"{best['item_matches']} histórico(s) com item parecido")
    if best["vehicle_matches"]:
        reason_parts.append(f"{best['vehicle_matches']} histórico(s) com equipamento parecido")
    if best["resolved_matches"]:
        reason_parts.append(f"{best['resolved_matches']} conclusão(ões) já executadas")
    return {
        "user_id": best["user_id"],
        "user": best["user"],
        "score": best["score"],
        "reason": " | ".join(reason_parts) if reason_parts else "Histórico parecido encontrado",
    }


def _item_label_for_work_order(item: MaintenanceScheduleItem) -> str:
    if item.checklist_item:
        return _clean(item.checklist_item.item_nome) or _clean(item.checklist_item.item_principal) or "Não conformidade"
    if item.activity:
        return _clean(item.activity.item_nome) or _clean(item.activity.titulo) or "Atividade"
    if item.schedule:
        return _clean(item.schedule.item_name) or _clean(item.schedule.title) or "Manutenção"
    return "Manutenção"


def _vehicle_family_from_type(value: str | None) -> str:
    normalized = _normalize_item_key_from_text(value)
    if normalized == "CAVALO":
        return "cavalo"
    if normalized == "CARRETA":
        return "carreta"
    return "ambos"


def _maintenance_vehicle_family(vehicle) -> str:
    """Retorna o código da família do ativo, priorizando o cadastro estruturado."""
    profile = getattr(vehicle, "equipment_profile", None) if vehicle else None
    family = getattr(profile, "family", None) if profile else None
    return str(getattr(family, "code", None) or getattr(vehicle, "tipo", None) or "").strip().lower()


def _normalize_family_filter(value: str | None) -> str | None:
    family = _clean(value)
    if not family:
        return None
    family = family.lower()
    if len(family) > 20 or any(not (char.isalnum() or char in "_-") for char in family):
        raise ValueError("Família de manutenção inválida.")
    return family


def _schedule_primary_package_id(schedule: MaintenanceSchedule | None) -> int | None:
    if not schedule:
        return None
    source_key = str(schedule.source_key or "")
    if not source_key.startswith(PACKAGE_SOURCE_PREFIX):
        return None
    package_ids = source_key.removeprefix(PACKAGE_SOURCE_PREFIX).split(",")
    return _parse_int(package_ids[0])


def _schedule_package_ids(schedule: MaintenanceSchedule | None) -> list[int]:
    if not schedule:
        return []
    return list(schedule.package_ids())


def _schedule_package_label(schedule: MaintenanceSchedule | None) -> str:
    if not schedule:
        return "-"
    return schedule.package_reference_label() or "-"


def _schedule_context_label(schedule: MaintenanceSchedule | None) -> str:
    if not schedule:
        return "Programação não encontrada"
    package_label = _schedule_package_label(schedule)
    if package_label != "-":
        return f"Prog #{schedule.id} | {package_label}"
    return f"Prog #{schedule.id} | {schedule.title}"


def _work_order_status_from_item(item: MaintenanceScheduleItem) -> str:
    mapping = {
        "PENDENTE": "ABERTA",
        "PROGRAMADO": "PROGRAMADA",
        "AGUARDANDO_MATERIAL": "AGUARDANDO_MATERIAL",
        "INSTALADO": "CONCLUIDA",
        "NAO_EXECUTADO": "NAO_EXECUTADA",
        "REPROGRAMADO": "REPROGRAMADA",
        "CANCELADO": "CANCELADA",
    }
    return mapping.get(str(item.status or "").upper(), "ABERTA")


def _sync_work_order_for_item(item: MaintenanceScheduleItem) -> MaintenanceWorkOrder:
    schedule = item.schedule
    if not schedule:
        raise ValueError("Item de manutenção sem programação vinculada.")

    work_order = item.work_order
    if not work_order:
        work_order = MaintenanceWorkOrder(
            order_number=f"OS-PEND-{item.id or 0}",
            schedule_id=schedule.id,
            schedule_item_id=item.id,
            resolution_package_id=_schedule_primary_package_id(schedule),
            vehicle_id=item.vehicle_id,
            opened_by_user_id=schedule.created_by_user_id,
            title=_clean(schedule.title) or "Ordem de serviço de manutenção",
            item_name=_item_label_for_work_order(item),
            status=_work_order_status_from_item(item),
            scheduled_date=item.scheduled_date,
            assigned_mechanic_user_id=item.assigned_mechanic_user_id or schedule.assigned_mechanic_user_id,
        )
        db.session.add(work_order)
        db.session.flush()
        work_order.order_number = f"OS-{work_order.id:06d}"
    else:
        work_order.schedule_id = schedule.id
        work_order.resolution_package_id = _schedule_primary_package_id(schedule)
        work_order.vehicle_id = item.vehicle_id
        work_order.opened_by_user_id = schedule.created_by_user_id
        work_order.title = _clean(schedule.title) or work_order.title or "Ordem de serviço de manutenção"
        work_order.item_name = _item_label_for_work_order(item)
        work_order.status = _work_order_status_from_item(item)
        work_order.scheduled_date = item.scheduled_date
        work_order.assigned_mechanic_user_id = item.assigned_mechanic_user_id or schedule.assigned_mechanic_user_id
        if not _clean(work_order.order_number):
            work_order.order_number = f"OS-{work_order.id:06d}"
    return work_order


def sync_work_order_for_item(item: MaintenanceScheduleItem) -> MaintenanceWorkOrder:
    """Public integration point used by operational modules that create maintenance items."""
    return _sync_work_order_for_item(item)


def _sync_schedule_work_orders(schedule: MaintenanceSchedule) -> None:
    for item in schedule.items:
        _sync_work_order_for_item(item)


def _ensure_work_orders_backfilled() -> None:
    rows = (
        MaintenanceScheduleItem.query.outerjoin(MaintenanceWorkOrder, MaintenanceWorkOrder.schedule_item_id == MaintenanceScheduleItem.id)
        .filter(MaintenanceWorkOrder.id.is_(None))
        .all()
    )
    if not rows:
        return
    for row in rows:
        _sync_work_order_for_item(row)
    db.session.commit()


def _open_work_order_statuses() -> set[str]:
    return {"ABERTA", "PROGRAMADA", "AGUARDANDO_MATERIAL", "EM_EXECUCAO", "REPROGRAMADA"}


def _open_item_statuses() -> set[str]:
    return {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}


def _build_oldest_open_work_orders(work_orders: list[MaintenanceWorkOrder], *, today: date) -> list[dict]:
    """Retorna uma fila curta de decisao, sem alterar a prioridade operacional da OS."""
    open_statuses = _open_work_order_statuses()
    rows = [row for row in work_orders if str(row.status or "").upper() in open_statuses]

    def reference_date(row: MaintenanceWorkOrder) -> date:
        return row.scheduled_date or (row.created_at.date() if row.created_at else today)

    prioritized = sorted(rows, key=lambda row: (reference_date(row), row.id))[:5]
    return [
        {
            "work_order_id": row.id,
            "order_number": row.order_number,
            "title": row.title,
            "status": row.status,
            "vehicle_id": row.vehicle_id,
            "vehicle_label": (row.vehicle.frota or row.vehicle.placa or f"Equipamento {row.vehicle_id}") if row.vehicle else f"Equipamento {row.vehicle_id}",
            "reference_date": reference_date(row).isoformat(),
            "reference_type": "DATA_PROGRAMADA" if row.scheduled_date else "DATA_DE_ABERTURA",
            "age_days": max((today - reference_date(row)).days, 0),
            "assigned_mechanic": row.assigned_mechanic.nome if row.assigned_mechanic else None,
        }
        for row in prioritized
    ]


def _build_maintenance_blockers(
    schedules: list[MaintenanceSchedule],
    work_orders: list[MaintenanceWorkOrder],
) -> list[dict]:
    rows: list[dict] = []
    open_item_statuses = _open_item_statuses()
    work_orders_by_schedule: dict[int, list[MaintenanceWorkOrder]] = {}
    for work_order in work_orders:
        work_orders_by_schedule.setdefault(int(work_order.schedule_id or 0), []).append(work_order)

    for schedule in schedules:
        open_items = [item for item in schedule.items if str(item.status or "").upper() in open_item_statuses]
        if not open_items:
            continue

        context_label = _schedule_context_label(schedule)
        blocked_materials = [
            link
            for link in schedule.materials
            if str(link.status or "").upper() in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}
        ]
        blocked_work_orders = [
            order
            for order in work_orders_by_schedule.get(int(schedule.id or 0), [])
            if str(order.status or "").upper() == "AGUARDANDO_MATERIAL"
        ]

        if not schedule.assigned_mechanic_user_id:
            rows.append(
                {
                    "type": "Sem responsável",
                    "reference": context_label,
                    "quantity": len(open_items),
                    "reading": "A programação está aberta, mas ainda sem mecânico responsável definido.",
                    "critical": False,
                }
            )
        if blocked_materials:
            rows.append(
                {
                    "type": "Material bloqueando",
                    "reference": context_label,
                    "quantity": len(blocked_materials),
                    "reading": "Existe peça aguardando compra ou liberação, então a execução ainda está travada.",
                    "critical": False,
                }
            )
        if blocked_work_orders:
            rows.append(
                {
                    "type": "OS bloqueada",
                    "reference": context_label,
                    "quantity": len(blocked_work_orders),
                    "reading": "Há ordem de serviço parada porque a peça ainda não liberou a execução.",
                    "critical": False,
                }
            )
    return rows


def build_mechanic_load_summary(mechanic_user_id: int | None, *, start_date: date | None = None, days: int = 7) -> dict | None:
    mechanic_id = _parse_int(mechanic_user_id)
    if not mechanic_id:
        return None

    today = today_manaus()
    start = start_date or today
    end = start + timedelta(days=max(days, 1) - 1)
    rows = (
        MaintenanceWorkOrder.query.filter(MaintenanceWorkOrder.assigned_mechanic_user_id == mechanic_id)
        .order_by(MaintenanceWorkOrder.scheduled_date.asc().nullslast(), MaintenanceWorkOrder.id.asc())
        .all()
    )
    open_statuses = _open_work_order_statuses()
    open_rows = [row for row in rows if str(row.status or "").upper() in open_statuses]
    overdue_rows = [
        row
        for row in open_rows
        if row.scheduled_date and row.scheduled_date < today
    ]
    window_rows = [
        row
        for row in open_rows
        if row.scheduled_date and start <= row.scheduled_date <= end
    ]
    by_day: dict[str, int] = {}
    for row in window_rows:
        if not row.scheduled_date:
            continue
        key = row.scheduled_date.isoformat()
        by_day[key] = by_day.get(key, 0) + 1

    mechanic = None
    if rows:
        mechanic = rows[0].assigned_mechanic
    return {
        "user_id": mechanic_id,
        "user": mechanic.to_dict() if mechanic else None,
        "open_work_orders": len(open_rows),
        "overdue_work_orders": len(overdue_rows),
        "scheduled_in_window": len(window_rows),
        "daily_window": by_day,
    }


def suggest_schedule_window(payload: dict) -> dict:
    start_date = _parse_date(payload.get("start_date") or payload.get("data_inicio"), default=today_manaus()) or today_manaus()
    daily_capacity = _normalize_daily_capacity(payload.get("daily_capacity") or payload.get("capacidade_diaria") or 1)
    mechanic_id = _parse_int(payload.get("assigned_mechanic_user_id") or payload.get("mecanico_id"))
    source_type = _normalize_type(payload.get("source_type") or payload.get("tipo") or payload.get("origem"))
    total_items = int(payload.get("selected_total") or 0)

    if total_items <= 0:
        package_ids = [int(value) for value in payload.get("package_ids") or []]
        activity_ids = [int(value) for value in payload.get("activity_ids") or []]
        vehicle_ids = [int(value) for value in payload.get("vehicle_ids") or []]
        checklist_item_ids = [int(value) for value in payload.get("checklist_item_ids") or []]
        if source_type == "PACOTE_RESOLUCAO" and package_ids:
            total_items = sum(len(package.links or []) for package in ResolutionPackage.query.filter(ResolutionPackage.id.in_(package_ids)).all())
        elif source_type == "ATIVIDADE" and activity_ids:
            total_items = sum(len(activity.items or []) for activity in Activity.query.filter(Activity.id.in_(activity_ids)).all())
        elif checklist_item_ids:
            total_items = len(checklist_item_ids)
        else:
            total_items = len(vehicle_ids)

    total_items = max(total_items, 0)
    if total_items <= 0:
        return {
            "suggested_start_date": start_date.isoformat(),
            "suggested_end_date": start_date.isoformat(),
            "total_items": 0,
            "daily_capacity": daily_capacity,
            "mechanic_load": build_mechanic_load_summary(mechanic_id, start_date=start_date),
            "reason": "Nenhum item selecionado para agenda.",
        }

    open_statuses = _open_work_order_statuses()
    day_loads: dict[date, int] = {}
    if mechanic_id:
        work_orders = (
            MaintenanceWorkOrder.query.filter(MaintenanceWorkOrder.assigned_mechanic_user_id == mechanic_id)
            .order_by(MaintenanceWorkOrder.scheduled_date.asc().nullslast())
            .all()
        )
        for row in work_orders:
            if row.scheduled_date and str(row.status or "").upper() in open_statuses:
                day_loads[row.scheduled_date] = day_loads.get(row.scheduled_date, 0) + 1

    allocated_dates: list[date] = []
    remaining = total_items
    cursor = start_date
    while remaining > 0:
        occupied = day_loads.get(cursor, 0)
        free_slots = max(daily_capacity - occupied, 0)
        if free_slots > 0:
            allocate = min(free_slots, remaining)
            allocated_dates.extend([cursor] * allocate)
            remaining -= allocate
        cursor = cursor + timedelta(days=1)

    suggested_start = allocated_dates[0] if allocated_dates else start_date
    suggested_end = allocated_dates[-1] if allocated_dates else start_date
    reason = "Agenda livre a partir da data solicitada."
    if mechanic_id and suggested_start > start_date:
        reason = "A agenda do mecânico já possui carga na data inicial. O sistema sugeriu a primeira janela com folga."
    elif mechanic_id:
        reason = "A agenda do mecânico ainda comporta este pacote dentro da capacidade diária."

    return {
        "suggested_start_date": suggested_start.isoformat(),
        "suggested_end_date": suggested_end.isoformat(),
        "total_items": total_items,
        "daily_capacity": daily_capacity,
        "mechanic_load": build_mechanic_load_summary(mechanic_id, start_date=suggested_start),
        "reason": reason,
    }


def suggest_material_for_schedule(schedule_id: int) -> dict | None:
    schedule = MaintenanceSchedule.query.get_or_404(schedule_id)
    target_item_names: set[str] = set()
    target_families: set[str] = set()

    if schedule.item_name:
        target_item_names.add(_normalize_item_key_from_text(schedule.item_name))
    for item in schedule.items:
        target_item_names.add(_normalize_item_key_from_text(_item_label_for_work_order(item)))
        vehicle_type = item.vehicle.tipo if item.vehicle else None
        target_families.add(_vehicle_family_from_type(vehicle_type))

    target_item_names.discard("")
    target_families.discard("")
    if not target_families:
        target_families.add("ambos")

    scores: dict[int, dict] = {}
    history_links = MaintenanceMaterial.query.order_by(MaintenanceMaterial.created_at.desc()).all()
    for link in history_links:
        material = link.material
        schedule_ref = link.schedule
        if not material or not schedule_ref:
            continue

        schedule_item_names = {_normalize_item_key_from_text(schedule_ref.item_name)}
        for schedule_item in schedule_ref.items:
            schedule_item_names.add(_normalize_item_key_from_text(_item_label_for_work_order(schedule_item)))
        schedule_item_names.discard("")

        score = 0
        item_matches = len(schedule_item_names.intersection(target_item_names))
        if item_matches:
            score += 5 * item_matches
        material_family = str(material.aplicacao_tipo or "ambos").lower()
        if material_family in target_families or material_family == "ambos":
            score += 2
        if str(link.status or "").upper() in {"UTILIZADO", "RESERVADO", "DISPONIVEL_EM_ESTOQUE"}:
            score += 1
        if score <= 0:
            continue

        entry = scores.setdefault(
            int(material.id),
            {
                "material": material.to_dict(),
                "score": 0,
                "item_matches": 0,
                "family_matches": 0,
                "quantity_per_vehicle": int(link.quantity_per_vehicle or 1),
                "history_count": 0,
            },
        )
        entry["score"] += score
        entry["item_matches"] += item_matches
        if material_family in target_families or material_family == "ambos":
            entry["family_matches"] += 1
        entry["history_count"] += 1
        if entry["history_count"] == 1:
            entry["quantity_per_vehicle"] = int(link.quantity_per_vehicle or 1)

    if scores:
        best = max(
            scores.values(),
            key=lambda row: (row["score"], row["item_matches"], row["family_matches"], row["history_count"]),
        )
        material = best["material"]
        return {
            "material": material,
            "quantity_per_vehicle": best["quantity_per_vehicle"],
            "status": "DISPONIVEL_EM_ESTOQUE" if int(material.get("quantidade_estoque") or 0) > 0 else "AGUARDANDO_MATERIAL",
            "reason": (
                f"{best['item_matches']} histórico(s) com item parecido | "
                f"{best['family_matches']} histórico(s) com família compatível"
            ),
            "strategy": "history",
        }

    fallback_materials = [
        material
        for material in Material.query.filter_by(ativo=True).order_by(Material.referencia.asc()).all()
        if str(material.aplicacao_tipo or "ambos").lower() in target_families or str(material.aplicacao_tipo or "ambos").lower() == "ambos"
    ]
    if not fallback_materials:
        fallback_materials = Material.query.filter_by(ativo=True).order_by(Material.referencia.asc()).all()
    if not fallback_materials:
        return None

    material = fallback_materials[0]
    return {
        "material": material.to_dict(),
        "quantity_per_vehicle": 1,
        "status": "DISPONIVEL_EM_ESTOQUE" if int(material.quantidade_estoque or 0) > 0 else "AGUARDANDO_MATERIAL",
        "reason": "Sem histórico suficiente. Aplicada regra simplificada pela peça padrão disponível para o item.",
        "strategy": "fallback",
    }


def build_work_order_report_payload(work_order_id: int) -> dict:
    work_order = MaintenanceWorkOrder.query.get_or_404(work_order_id)
    schedule = work_order.schedule
    item = work_order.schedule_item
    vehicle = work_order.vehicle
    materials = schedule.materials if schedule else []
    material_text = "; ".join(
        f"{(link.material.referencia if link.material else '-') } | {(link.material.descricao if link.material else '-') } | "
        f"Qtd/veículo {int(link.quantity_per_vehicle or 0)} | Status {str(link.status or '-').replace('_', ' ')}"
        for link in materials
    ) or "Sem peça vinculada"

    rows = [
        {"campo": "Número da OS", "valor": work_order.order_number},
        {"campo": "Programação", "valor": schedule.title if schedule else "-"},
        {"campo": "Pacote de resolução", "valor": f"#{work_order.resolution_package_id}" if work_order.resolution_package_id else "-"},
        {"campo": "Serviço", "valor": work_order.item_name or "-"},
        {"campo": "Veículo", "valor": f"{vehicle.frota if vehicle else '-'} | {vehicle.placa if vehicle else '-'} | {vehicle.modelo if vehicle else '-'}"},
        {"campo": "Situação da OS", "valor": str(work_order.status or "-").replace("_", " ")},
        {"campo": "Situação da manutenção", "valor": str(schedule.status or "-").replace("_", " ") if schedule else "-"},
        {"campo": "Mecânico responsável", "valor": (work_order.assigned_mechanic.nome if work_order.assigned_mechanic else "-")},
        {"campo": "Data programada", "valor": work_order.scheduled_date.strftime("%d/%m/%Y") if work_order.scheduled_date else "-"},
        {"campo": "Aberta por", "valor": (work_order.opened_by.nome if work_order.opened_by else "-")},
        {"campo": "Aberta em", "valor": work_order.created_at.strftime("%d/%m/%Y %H:%M") if work_order.created_at else "-"},
        {"campo": "Peças e materiais", "valor": material_text},
        {"campo": "Observação técnica", "valor": item.observation if item else "-"},
        {"campo": "Motivo de não execução", "valor": item.not_executed_reason if item else "-"},
        {"campo": "Foto antes", "valor": ((item.checklist_item.foto_antes if item and item.checklist_item else None) or "-")},
        {"campo": "Foto depois", "valor": ((item.photo_after if item else None) or "-")},
        {"campo": "Executado por", "valor": (item.executed_by.nome if item and item.executed_by else "-")},
        {"campo": "Executado em", "valor": item.executed_at.strftime("%d/%m/%Y %H:%M") if item and item.executed_at else "-"},
    ]
    return {
        "title": f"Ordem de Serviço {work_order.order_number}",
        "subtitle": f"{work_order.item_name or 'Manutenção'} | {vehicle.frota if vehicle else '-'}",
        "period_label": work_order.scheduled_date.strftime("%d/%m/%Y") if work_order.scheduled_date else "Sem data programada",
        "columns": [("Campo", "campo"), ("Valor", "valor")],
        "rows": rows,
        "filename": f"ordem_servico_{work_order.order_number.lower()}.pdf",
    }

def _refresh_schedule_materials(schedule: MaintenanceSchedule) -> None:
    total_items = max(len(schedule.items), 1)
    for link in schedule.materials:
        material = link.material
        total_required = int(link.quantity_per_vehicle or 1) * total_items
        installed_items = sum(1 for item in schedule.items if item.status == "INSTALADO")
        used_quantity = int(link.quantity_per_vehicle or 1) * installed_items
        remaining_required = max(total_required - used_quantity, 0)
        link.quantity_required = total_required
        if not material:
            link.status = "AGUARDANDO_MATERIAL"
            continue
        if remaining_required <= 0 and installed_items:
            link.status = "UTILIZADO"
            link.quantity_reserved = max(link.quantity_reserved or 0, used_quantity)
        elif (link.quantity_reserved or 0) >= remaining_required:
            link.status = "RESERVADO"
        elif material.quantidade_estoque >= remaining_required:
            link.status = "DISPONIVEL_EM_ESTOQUE"
        elif link.status != "EM_COMPRAS":
            link.status = "AGUARDANDO_MATERIAL"


def recalculate_schedule(schedule: MaintenanceSchedule) -> MaintenanceSchedule:
    _refresh_schedule_materials(schedule)
    materials = schedule.materials
    items = schedule.items

    if items and all(item.status == "INSTALADO" for item in items):
        schedule.status = "CONCLUIDA"
    elif any(item.status == "INSTALADO" for item in items):
        schedule.status = "EM_EXECUCAO"
    elif any(material.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"} for material in materials):
        schedule.status = "AGUARDANDO_MATERIAL"
    elif any(item.status == "PROGRAMADO" for item in items):
        schedule.status = "PROGRAMADA"
    else:
        schedule.status = "ABERTA"
    return schedule


def _build_month_calendar(items: list[MaintenanceScheduleItem], *, year: int, month: int) -> dict:
    total_days = monthrange(year, month)[1]
    grouped: dict[str, list[MaintenanceScheduleItem]] = {
        date(year, month, day_number).isoformat(): []
        for day_number in range(1, total_days + 1)
    }

    for item in items:
        if not item.scheduled_date:
            continue
        key = item.scheduled_date.isoformat()
        grouped.setdefault(key, []).append(item)

    days = []
    for day_number in range(1, total_days + 1):
        current = date(year, month, day_number)
        rows = grouped.get(current.isoformat(), [])
        days.append(
            {
                "date": current.isoformat(),
                "day": day_number,
                "items": [item.to_dict() for item in rows],
                "total": len(rows),
                "pendentes": sum(1 for item in rows if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}),
                "instalados": sum(1 for item in rows if item.status == "INSTALADO"),
                "nao_executados": sum(1 for item in rows if item.status == "NAO_EXECUTADO"),
                "aguardando_material": sum(1 for item in rows if item.status == "AGUARDANDO_MATERIAL"),
            }
        )
    return {"days": days}


def build_maintenance_overview(
    *,
    year: int | None = None,
    month: int | None = None,
    assigned_to_user_id: int | None = None,
    family: str | None = None,
    exclude_checklist: bool = False,
) -> dict:
    _ensure_work_orders_backfilled()
    today = today_manaus()
    year = year or today.year
    month = month or today.month
    family_filter = _normalize_family_filter(family)
    # As relações da manutenção têm várias associações profundas configuradas
    # como eager loading. No SQLite isso pode ultrapassar o limite de 64 tabelas
    # em um único JOIN. A visão só precisa dos registros e serializa os detalhes
    # depois, em consultas menores.
    schedules = (
        MaintenanceSchedule.query.options(lazyload("*"))
        .order_by(MaintenanceSchedule.created_at.desc())
        .all()
    )
    items = MaintenanceScheduleItem.query.order_by(MaintenanceScheduleItem.scheduled_date.asc().nullslast()).all()
    materials = MaintenanceMaterial.query.order_by(MaintenanceMaterial.created_at.desc()).all()
    work_orders = MaintenanceWorkOrder.query.order_by(MaintenanceWorkOrder.scheduled_date.asc().nullslast(), MaintenanceWorkOrder.id.asc()).all()

    if exclude_checklist:
        checklist_schedule_ids = {schedule.id for schedule in schedules if schedule.source_type == "CHECKLIST_NC"}
        schedules = [schedule for schedule in schedules if schedule.id not in checklist_schedule_ids]
        items = [item for item in items if item.schedule_id not in checklist_schedule_ids]
        materials = [material for material in materials if material.schedule_id not in checklist_schedule_ids]
        work_orders = [row for row in work_orders if row.schedule_id not in checklist_schedule_ids]

    items = [
        item
        for item in items
        if item.scheduled_date and item.scheduled_date.year == year and item.scheduled_date.month == month
    ]

    if assigned_to_user_id:
        schedules = [
            schedule
            for schedule in schedules
            if schedule.assigned_mechanic_user_id == assigned_to_user_id
            or any(item.assigned_mechanic_user_id == assigned_to_user_id for item in schedule.items)
        ]
        items = [
            item
            for item in items
            if item.assigned_mechanic_user_id == assigned_to_user_id
            or (item.schedule and item.schedule.assigned_mechanic_user_id == assigned_to_user_id)
        ]
        work_orders = [row for row in work_orders if row.assigned_mechanic_user_id == assigned_to_user_id]

    if family_filter:
        items = [item for item in items if _maintenance_vehicle_family(item.vehicle) == family_filter]
        item_ids = {item.id for item in items}
        schedule_ids = {item.schedule_id for item in items if item.schedule_id}
        schedules = [schedule for schedule in schedules if schedule.id in schedule_ids]
        materials = [material for material in materials if material.schedule_id in schedule_ids]
        work_orders = [
            row for row in work_orders
            if row.schedule_item_id in item_ids or _maintenance_vehicle_family(row.vehicle) == family_filter
        ]

    programmed = [item for item in items if item.scheduled_date]
    installed = sum(1 for item in items if item.status == "INSTALADO")
    not_executed = sum(1 for item in items if item.status == "NAO_EXECUTADO")
    pending = sum(1 for item in items if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"})
    days_used = len({item.scheduled_date for item in programmed})
    total_done = installed + not_executed
    completion_base = len(items) or 1
    open_order_statuses = _open_work_order_statuses()
    open_work_orders = [row for row in work_orders if str(row.status or "").upper() in open_order_statuses]
    overdue_work_orders = [row for row in open_work_orders if row.scheduled_date and row.scheduled_date < today]
    blocked_work_orders = [row for row in work_orders if str(row.status or "").upper() == "AGUARDANDO_MATERIAL"]
    completed_work_orders = [row for row in work_orders if str(row.status or "").upper() == "CONCLUIDA"]
    oldest_open_work_orders = _build_oldest_open_work_orders(work_orders, today=today)
    blockers = _build_maintenance_blockers(schedules, work_orders)

    return {
        "periodo": {
            "ano": year,
            "mes": month,
            "rotulo": _month_label(year, month),
        },
        "resumo": {
            "programacoes": len(schedules),
            "itens": len(items),
            "materiais": len(materials),
            "aguardando_material": sum(1 for material in materials if material.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}),
            "programados": len(programmed),
            "instalados": installed,
            "nao_executados": not_executed,
            "pendentes": pending,
            "reprogramados": sum(1 for item in items if item.status == "REPROGRAMADO"),
            "dias_utilizados": days_used,
            "capacidade_media": round(len(programmed) / days_used, 1) if days_used else 0,
            "percentual_conclusao": round((total_done / completion_base) * 100, 1) if items else 0,
            "os_abertas": len(open_work_orders),
            "os_atrasadas": len(overdue_work_orders),
            "os_bloqueadas": len(blocked_work_orders),
            "os_concluidas": len(completed_work_orders),
        },
        "cronograma": _build_month_calendar(items, year=year, month=month),
        "programacoes": [schedule.to_dict(include_items=True, include_materials=True) for schedule in schedules],
        "itens": [item.to_dict() for item in items],
        "materiais": [material.to_dict() for material in materials],
        "bloqueios": blockers,
        "backlog_prioritario": {
            "os_mais_antigas": oldest_open_work_orders,
            "criterio": "OS aberta ordenada pela data programada; sem data programada, usa a data de abertura.",
        },
    }


def _distribute_dates(start_date: date, total_items: int, daily_capacity: int) -> list[date]:
    assigned_dates: list[date] = []
    current = start_date
    count_on_day = 0
    for _ in range(total_items):
        assigned_dates.append(current)
        count_on_day += 1
        if count_on_day >= daily_capacity:
            current = current + timedelta(days=1)
            count_on_day = 0
    return assigned_dates


def _ensure_preventive_wash_queue_items(schedule: MaintenanceSchedule) -> None:
    if schedule.source_type != "PREVENTIVA":
        return

    existing_by_vehicle = {item.vehicle_id: item for item in WashQueueItem.query.all()}
    max_position = db.session.query(db.func.max(WashQueueItem.queue_position)).scalar() or 0
    for schedule_item in schedule.items:
        if schedule_item.vehicle_id in existing_by_vehicle:
            continue
        vehicle = schedule_item.vehicle
        if not vehicle:
            continue
        max_position += 1
        queue_item = WashQueueItem(
            vehicle_id=vehicle.id,
            referencia=vehicle.frota,
            categoria="cavalo" if str(vehicle.tipo or "").lower() == "cavalo" else "auxiliar",
            queue_position=max_position,
        )
        db.session.add(queue_item)
        existing_by_vehicle[vehicle.id] = queue_item


def create_maintenance_schedule(payload: dict, *, created_by_user_id: int) -> MaintenanceSchedule:
    source_type = _normalize_type(payload.get("source_type") or payload.get("tipo") or payload.get("origem"))
    source_key = _clean(payload.get("source_key") or payload.get("chave_origem"))
    start_date = _parse_date(payload.get("start_date") or payload.get("data_inicio"), default=today_manaus())
    daily_capacity = _normalize_daily_capacity(payload.get("daily_capacity") or payload.get("capacidade_diaria"))

    # A tabela legada aceita ATIVIDADE. A chave especial preserva a origem
    # correta para calendário, OS e relatórios sem exigir migração destrutiva.
    if source_type == "CORRETIVA_PROGRAMADA":
        source_type = "ATIVIDADE"
        source_key = source_key or f"{PLANNED_CORRECTIVE_SOURCE_PREFIX}{uuid4().hex}"
        if not source_key.startswith(PLANNED_CORRECTIVE_SOURCE_PREFIX):
            source_key = f"{PLANNED_CORRECTIVE_SOURCE_PREFIX}{source_key}"

    if source_type in {"ATIVIDADE", "CHECKLIST_NC"}:
        if not (source_type == "ATIVIDADE" and source_key and source_key.startswith(PLANNED_CORRECTIVE_SOURCE_PREFIX)):
            raise ValueError(
                "Novas resoluções corretivas devem entrar pela Central de Resolução, virar Pacote de Resolução e só depois seguir para a manutenção."
            )

    package_ids = [int(value) for value in payload.get("package_ids") or []]
    selected_packages: list[ResolutionPackage] = []
    if source_type == "PACOTE_RESOLUCAO":
        if not package_ids:
            raise ValueError("Selecione ao menos um pacote de resolução.")
        selected_packages = (
            ResolutionPackage.query.filter(ResolutionPackage.id.in_(package_ids))
            .order_by(ResolutionPackage.created_at.desc())
            .all()
        )
        if len(selected_packages) != len(set(package_ids)):
            raise ValueError("Um ou mais pacotes de resolução não foram encontrados.")
        open_package_statuses = {"ABERTO", "EM_MANUTENCAO"}
        invalid_status = [package for package in selected_packages if package.status not in open_package_statuses]
        if invalid_status:
            raise ValueError("Somente pacotes abertos ou já enviados para manutenção podem ser programados.")
        source_key = f"{PACKAGE_SOURCE_PREFIX}{','.join(str(package.id) for package in sorted(selected_packages, key=lambda row: row.id))}"
        source_type = "CHECKLIST_NC"

    if source_key:
        existing_schedule = MaintenanceSchedule.query.filter_by(source_type=source_type, source_key=source_key).first()
        if existing_schedule:
            raise ValueError(f"Já existe programação aberta para esta origem: #{existing_schedule.id}.")

    schedule = MaintenanceSchedule(
        source_type=source_type,
        source_key=source_key,
        title=_clean(payload.get("title") or payload.get("titulo")) or "Programação de manutenção",
        item_name=_clean(payload.get("item_name") or payload.get("item_nome")),
        status=_normalize_status(payload.get("status"), default="ABERTA"),
        start_date=start_date,
        end_date=None,
        daily_capacity=daily_capacity,
        created_by_user_id=created_by_user_id,
        assigned_mechanic_user_id=payload.get("assigned_mechanic_user_id"),
        observation=_clean(payload.get("observation") or payload.get("observacao")),
    )
    db.session.add(schedule)
    db.session.flush()

    checklist_item_ids = [int(value) for value in payload.get("checklist_item_ids") or []]
    activity_ids = [int(value) for value in payload.get("activity_ids") or []]
    vehicle_ids = [int(value) for value in payload.get("vehicle_ids") or []]

    source_items: list[tuple[int, int | None, int | None]] = []
    if selected_packages:
        seen_checklist_ids: set[int] = set()
        for package in selected_packages:
            for link in package.links:
                checklist_item = link.checklist_item
                if not checklist_item or checklist_item.id in seen_checklist_ids:
                    continue
                vehicle_id = checklist_item.checklist.vehicle_id if checklist_item.checklist else None
                if not vehicle_id:
                    continue
                source_items.append((vehicle_id, checklist_item.id, None))
                seen_checklist_ids.add(checklist_item.id)
    elif checklist_item_ids:
        raise ValueError(
            "Abertura direta por não conformidade foi desativada neste fluxo. Use a Central de Resolução para gerar pacote e enviar para a manutenção."
        )
    elif activity_ids:
        raise ValueError(
            "Abertura direta por inspeção foi desativada neste fluxo. Use a Central de Resolução para gerar pacote e enviar para a manutenção."
        )
    elif vehicle_ids:
        for vehicle_id in vehicle_ids:
            source_items.append((vehicle_id, None, None))
    else:
        raise ValueError("Selecione ao menos um pacote de resolução ou veículo para preventiva.")

    selected_checklist_ids = [checklist_item_id for _, checklist_item_id, _ in source_items if checklist_item_id]
    if selected_checklist_ids:
        existing_schedule_items = (
            MaintenanceScheduleItem.query.filter(MaintenanceScheduleItem.checklist_item_id.in_(selected_checklist_ids))
            .all()
        )
        if existing_schedule_items:
            schedule_ids = sorted({row.schedule_id for row in existing_schedule_items if row.schedule_id})
            joined_ids = ", ".join(f"#{schedule_id}" for schedule_id in schedule_ids)
            raise ValueError(f"Já existe programação de manutenção para parte dos registros selecionados: {joined_ids}.")

    assigned_dates = _distribute_dates(start_date, len(source_items), daily_capacity)
    for index, (vehicle_id, checklist_item_id, activity_id) in enumerate(source_items):
        db.session.add(
            MaintenanceScheduleItem(
                schedule_id=schedule.id,
                vehicle_id=vehicle_id,
                checklist_item_id=checklist_item_id,
                activity_id=activity_id,
                scheduled_date=assigned_dates[index],
                status="PROGRAMADO",
                assigned_mechanic_user_id=schedule.assigned_mechanic_user_id,
                observation=schedule.observation,
            )
        )

    schedule.end_date = assigned_dates[-1] if assigned_dates else start_date
    db.session.flush()
    _sync_schedule_work_orders(schedule)

    for package in selected_packages:
        package.status = "EM_MANUTENCAO"

    _ensure_preventive_wash_queue_items(schedule)
    recalculate_schedule(schedule)
    db.session.commit()
    return schedule


def program_maintenance_schedule(schedule_id: int, payload: dict, *, user_id: int) -> MaintenanceSchedule:
    schedule = MaintenanceSchedule.query.get_or_404(schedule_id)
    start_date = _parse_date(payload.get("start_date") or payload.get("data_inicio"), default=schedule.start_date or today_manaus())
    if not start_date:
        start_date = today_manaus()
    daily_capacity = _normalize_daily_capacity(
        payload.get("daily_capacity") or payload.get("capacidade_diaria") or schedule.daily_capacity
    )

    assigned_mechanic = payload.get("assigned_mechanic_user_id")
    if assigned_mechanic is not None:
        schedule.assigned_mechanic_user_id = int(assigned_mechanic) if str(assigned_mechanic).strip() else None

    programmable_items = [
        item
        for item in sorted(schedule.items, key=lambda row: (row.scheduled_date or date.max, row.id))
        if item.status not in {"INSTALADO", "CANCELADO"}
    ]
    assigned_dates = _distribute_dates(start_date, len(programmable_items), daily_capacity)
    for index, item in enumerate(programmable_items):
        item.scheduled_date = assigned_dates[index]
        item.status = "PROGRAMADO" if item.status in {"PENDENTE", "AGUARDANDO_MATERIAL", "REPROGRAMADO", "NAO_EXECUTADO"} else item.status
        item.assigned_mechanic_user_id = schedule.assigned_mechanic_user_id

    schedule.start_date = assigned_dates[0] if assigned_dates else start_date
    schedule.end_date = assigned_dates[-1] if assigned_dates else start_date
    schedule.daily_capacity = daily_capacity
    db.session.flush()
    _sync_schedule_work_orders(schedule)
    _ensure_preventive_wash_queue_items(schedule)
    recalculate_schedule(schedule)
    db.session.commit()
    return schedule


def reprogram_schedule_item(item_id: int, payload: dict, *, user) -> MaintenanceScheduleItem:
    item = MaintenanceScheduleItem.query.get_or_404(item_id)
    scheduled_date = _parse_date(payload.get("scheduled_date") or payload.get("data"))
    if not scheduled_date:
        raise ValueError("Informe a nova data do cronograma.")
    reason = _clean(payload.get("reason") or payload.get("motivo") or payload.get("observation") or payload.get("observacao"))
    if not reason:
        raise ValueError("Informe o motivo da reprogramacao.")

    assigned_mechanic = payload.get("assigned_mechanic_user_id")
    if assigned_mechanic is not None:
        item.assigned_mechanic_user_id = int(assigned_mechanic) if str(assigned_mechanic).strip() else None

    previous_date = item.scheduled_date.isoformat() if item.scheduled_date else "sem data"
    item.scheduled_date = scheduled_date
    if item.status not in {"INSTALADO", "CANCELADO"}:
        item.status = "REPROGRAMADO"
    item.observation = reason
    db.session.flush()
    _sync_work_order_for_item(item)
    recalculate_schedule(item.schedule)
    record_event(
        user_id=getattr(user, "id", None),
        entity_type="MAINTENANCE_SCHEDULE_ITEM",
        entity_id=item.id,
        action="REPROGRAMMED",
        old_value=f"data={previous_date}",
        new_value=f"data={scheduled_date.isoformat()}; motivo={reason}",
    )
    db.session.commit()
    return item


def link_schedule_material(schedule_id: int, payload: dict, *, user_id: int) -> MaintenanceMaterial:
    schedule = MaintenanceSchedule.query.get_or_404(schedule_id)
    material_id = payload.get("material_id")
    if not material_id:
        raise ValueError("Informe o material.")

    material = Material.query.get(material_id)
    if not material or not material.ativo:
        raise ValueError("Material informado e invalido ou esta inativo.")
    for item in schedule.items:
        from app.services.supply_library_service import material_is_applicable_to_vehicle
        if not material_is_applicable_to_vehicle(material, item.vehicle_id):
            raise ValueError("Este material não está liberado para a família de um ou mais equipamentos da programação.")

    quantity_per_vehicle = int(payload.get("quantity_per_vehicle") or payload.get("quantidade_por_veiculo") or 1)
    if quantity_per_vehicle <= 0:
        raise ValueError("A quantidade por veículo deve ser maior que zero.")

    total_required = quantity_per_vehicle * max(len(schedule.items), 1)
    existing = MaintenanceMaterial.query.filter_by(schedule_id=schedule.id, material_id=material.id).first()
    if existing:
        existing.quantity_per_vehicle = quantity_per_vehicle
        existing.quantity_required = total_required
        existing.status = _normalize_material_status(payload.get("status"), default=existing.status)
        existing.observation = _clean(payload.get("observation") or payload.get("observacao")) or existing.observation
        link = existing
    else:
        status = _normalize_material_status(payload.get("status"), default="AGUARDANDO_MATERIAL")
        if material.quantidade_estoque >= total_required and status == "AGUARDANDO_MATERIAL":
            status = "DISPONIVEL_EM_ESTOQUE"
        link = MaintenanceMaterial(
            schedule_id=schedule.id,
            material_id=material.id,
            quantity_per_vehicle=quantity_per_vehicle,
            quantity_required=total_required,
            quantity_reserved=0,
            status=status,
            observation=_clean(payload.get("observation") or payload.get("observacao")),
        )
        db.session.add(link)

    if link.status == "DISPONIVEL_EM_ESTOQUE" and material.quantidade_estoque >= total_required:
        link.quantity_reserved = total_required
    elif material.quantidade_estoque < total_required:
        link.status = "EM_COMPRAS"
    if not _clean(link.observation):
        link.observation = (
            f"{_schedule_context_label(schedule)} | "
            f"Peça prevista para {schedule.vehicle_family()} | "
            f"Qtd por veículo {quantity_per_vehicle}"
        )

    recalculate_schedule(schedule)
    db.session.commit()
    return link


def _can_execute_with_material(item: MaintenanceScheduleItem) -> tuple[bool, str | None]:
    schedule = item.schedule
    if not schedule:
        return False, "Programação não encontrada."

    _refresh_schedule_materials(schedule)
    for link in schedule.materials:
        material = link.material
        required = int(link.quantity_per_vehicle or 1)
        if not material:
            return False, "Material vinculado não encontrado."
        if link.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}:
            return False, f"Material ainda não liberado para {material.referencia}."
        if material.quantidade_estoque < required:
            return False, f"Material insuficiente para {material.referencia}."
    return True, None


def update_schedule_item(item_id: int, payload: dict, *, user) -> MaintenanceScheduleItem:
    item = MaintenanceScheduleItem.query.get_or_404(item_id)
    new_status = _normalize_item_status(payload.get("status") or payload.get("status_execucao"))
    item.observation = _clean(payload.get("observation") or payload.get("observacao")) or item.observation
    item.not_executed_reason = _clean(payload.get("not_executed_reason") or payload.get("motivo")) or item.not_executed_reason
    item.photo_after = _clean(payload.get("photo_after") or payload.get("foto_depois")) or item.photo_after
    item.assigned_mechanic_user_id = payload.get("assigned_mechanic_user_id") or item.assigned_mechanic_user_id

    if new_status == "INSTALADO":
        allowed, message = _can_execute_with_material(item)
        if not allowed:
            raise ValueError(message or "Material indisponível para concluir a instalação.")
        work_order = item.work_order
        work_order_label = work_order.order_number if work_order and work_order.order_number else "OS sem número"
        package_label = _schedule_package_label(item.schedule)
        vehicle_label = item.vehicle.frota if item.vehicle and item.vehicle.frota else f"Veículo {item.vehicle_id}"
        for link in item.schedule.materials:
            required = int(link.quantity_per_vehicle or 1)
            from app.services.supply_library_service import consume_warehouse_reservation
            consume_warehouse_reservation(link.id, required)
            register_material_movement(
                link.material,
                quantity=required,
                movement_type="ATIVIDADE",
                delta=-required,
                observation=(
                    f"Baixa para manutenção: {item.schedule.title} | "
                    f"{package_label} | {work_order_label} | {vehicle_label}"
                ),
                activity_id=item.activity_id,
                checklist_item_id=item.checklist_item_id,
            )
            link.quantity_reserved = min(int(link.quantity_required or required), int(link.quantity_reserved or 0) + required)
        if item.checklist_item:
            item.checklist_item.resolvido = True
            item.checklist_item.data_resolucao = now_manaus_naive()
            item.checklist_item.resolved_by_user_id = user.id
            item.checklist_item.foto_depois = item.photo_after or item.checklist_item.foto_depois
            if item.observation:
                current_observation = item.checklist_item.observacao or ""
                suffix = f"Resolução de manutenção: {item.observation}"
                if suffix not in current_observation:
                    item.checklist_item.observacao = f"{current_observation}\n{suffix}".strip()
        item.executed_by_user_id = user.id
        item.executed_at = now_manaus_naive()
        item.status = "INSTALADO"
    elif new_status == "NAO_EXECUTADO":
        item.status = new_status
        item.executed_by_user_id = user.id
        item.executed_at = now_manaus_naive()
        if not item.not_executed_reason:
            raise ValueError("Informe o motivo para marcar como não executado.")
    else:
        item.status = new_status

    db.session.flush()
    _sync_work_order_for_item(item)
    recalculate_schedule(item.schedule)
    if item.status == "INSTALADO":
        from app.services.pcm_service import advance_preventive_plan_after_completion
        advance_preventive_plan_after_completion(item)
    db.session.commit()
    return item


def mechanic_items_for_user(user_id: int) -> list[MaintenanceScheduleItem]:
    _ensure_work_orders_backfilled()
    rows = MaintenanceScheduleItem.query.order_by(MaintenanceScheduleItem.scheduled_date.asc().nullslast()).all()
    return [
        item
        for item in rows
        if item.assigned_mechanic_user_id == user_id
        or (item.schedule and item.schedule.assigned_mechanic_user_id == user_id)
    ]


def build_vehicle_maintenance_history(vehicle_id: int) -> dict:
    _ensure_work_orders_backfilled()
    items = (
        MaintenanceScheduleItem.query.filter_by(vehicle_id=vehicle_id)
        .order_by(MaintenanceScheduleItem.scheduled_date.desc().nullslast(), MaintenanceScheduleItem.created_at.desc())
        .all()
    )
    return {
        "manutencoes": [item.to_dict() for item in items],
    }


def _maintenance_report_items(*, year: int | None = None, month: int | None = None) -> list[MaintenanceScheduleItem]:
    _ensure_work_orders_backfilled()
    query = MaintenanceScheduleItem.query.order_by(MaintenanceScheduleItem.scheduled_date.desc().nullslast(), MaintenanceScheduleItem.id.desc())
    if year:
        query = query.filter(db.extract("year", MaintenanceScheduleItem.scheduled_date) == year)
    if month:
        query = query.filter(db.extract("month", MaintenanceScheduleItem.scheduled_date) == month)
    return query.all()


def _item_report_row(item: MaintenanceScheduleItem) -> dict:
    schedule = item.schedule
    vehicle = item.vehicle
    materials = schedule.materials if schedule else []
    material_label = "; ".join(
        f"{link.material.referencia if link.material else '-'} ({link.quantity_per_vehicle} por veículo)"
        for link in materials
    ) or "-"
    return {
        "data": item.scheduled_date.strftime("%d/%m/%Y") if item.scheduled_date else "-",
        "veiculo": vehicle.frota if vehicle else "-",
        "placa": vehicle.placa if vehicle else "-",
        "tipo": _schedule_source_origin_type(schedule).replace("_", " ").title() if schedule else "-",
        "programacao": schedule.title if schedule else "-",
        "status": item.status.replace("_", " "),
        "mecanico": (item.assigned_mechanic.nome if item.assigned_mechanic else None)
        or (schedule.assigned_mechanic.nome if schedule and schedule.assigned_mechanic else "-"),
        "materiais": material_label,
        "parecer": item.observation or item.not_executed_reason or "-",
    }


def build_maintenance_report_payload(
    *,
    report_type: str = "mensal",
    year: int | None = None,
    month: int | None = None,
    mechanic_id: int | None = None,
    vehicle_id: int | None = None,
) -> dict:
    today = today_manaus()
    year = year or today.year
    month = month or today.month
    normalized_type = (report_type or "mensal").strip().lower()
    items = _maintenance_report_items(year=year, month=month)

    if normalized_type == "preventiva":
        items = [item for item in items if item.schedule and item.schedule.source_type == "PREVENTIVA"]
    elif normalized_type == "mecanico":
        if mechanic_id:
            items = [
                item
                for item in items
                if item.assigned_mechanic_user_id == mechanic_id or (item.schedule and item.schedule.assigned_mechanic_user_id == mechanic_id)
            ]
    elif normalized_type == "veiculo":
        if vehicle_id:
            items = [item for item in items if item.vehicle_id == vehicle_id]
    elif normalized_type == "material":
        items = [item for item in items if item.schedule and item.schedule.materials]
    elif normalized_type == "pendencias":
        items = [item for item in items if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO", "NAO_EXECUTADO"}]

    titles = {
        "mensal": "Relatório mensal de manutenção",
        "preventiva": "Relatório de preventiva",
        "mecanico": "Relatório por mecânico",
        "veiculo": "Relatório por veículo",
        "material": "Relatório de materiais utilizados",
        "pendencias": "Relatório de pendências",
    }
    columns = [
        ("Data", "data"),
        ("Veículo", "veiculo"),
        ("Placa", "placa"),
        ("Tipo", "tipo"),
        ("Programação", "programacao"),
        ("Status", "status"),
        ("Mecânico", "mecanico"),
        ("Materiais", "materiais"),
        ("Parecer", "parecer"),
    ]
    return {
        "title": titles.get(normalized_type, titles["mensal"]),
        "subtitle": f"{_month_label(year, month).title()} | {len(items)} registros",
        "period_label": _month_label(year, month).title(),
        "columns": columns,
        "rows": [_item_report_row(item) for item in items],
        "filename": f"relatorio_manutencao_{normalized_type}_{year}_{month:02d}.pdf",
    }

