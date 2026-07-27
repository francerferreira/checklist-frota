from __future__ import annotations

from collections import Counter
from datetime import date
from time import monotonic

from sqlalchemy import func

from app.models import (
    EquipmentFamily,
    EquipmentProfile,
    MaintenanceMaterial,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    PreventivePlan,
    PurchaseRequest,
    Vehicle,
)
from app.services.maintenance_dashboard_service import (
    OPEN_ORDER_STATUSES,
    DashboardFilters,
    _reliability_metrics,
)
from app.services.pcm_service import build_backlog, plan_due_state
from app.utils.timezone import now_manaus_naive, today_manaus


TV_FAMILY_CODES = ("lbs", "rtg")
TV_CACHE_TTL_SECONDS = 15
_payload_cache: dict[tuple, tuple[float, dict]] = {}


def _cache_key(filters: DashboardFilters) -> tuple:
    return (
        filters.date_from.isoformat(),
        filters.date_to.isoformat(),
        filters.family_id,
        filters.vehicle_id,
        filters.location_id,
    )


def _scoped_vehicles(filters: DashboardFilters) -> list[Vehicle]:
    query = (
        Vehicle.query
        .join(Vehicle.equipment_profile)
        .join(EquipmentProfile.family)
        .filter(Vehicle.ativo.is_(True), func.lower(EquipmentFamily.code).in_(TV_FAMILY_CODES))
    )
    if filters.family_id:
        query = query.filter(EquipmentProfile.family_id == filters.family_id)
    if filters.vehicle_id:
        query = query.filter(Vehicle.id == filters.vehicle_id)
    if filters.location_id:
        query = query.filter(EquipmentProfile.operational_location_id == filters.location_id)
    return query.order_by(Vehicle.frota.asc()).all()


def _vehicle_summary(vehicle: Vehicle) -> dict:
    profile = vehicle.equipment_profile
    state = vehicle.operational_state
    return {
        "id": vehicle.id,
        "frota": vehicle.frota,
        "family": (profile.family.code or "").upper() if profile and profile.family else "SEM_FAMILIA",
        "family_name": profile.family.name if profile and profile.family else "Sem família",
        "location": profile.location.full_name() if profile and profile.location else "Sem local",
        "criticality": profile.criticality if profile else "MEDIA",
        "status": state.operational_status if state else "SEM_APONTAMENTO",
        "status_reason": state.status_reason if state else None,
        "status_updated_at": state.status_updated_at.isoformat() if state and state.status_updated_at else None,
    }


def _open_orders(vehicle_ids: list[int]) -> list[MaintenanceWorkOrder]:
    if not vehicle_ids:
        return []
    return (
        MaintenanceWorkOrder.query
        .filter(MaintenanceWorkOrder.vehicle_id.in_(vehicle_ids))
        .order_by(MaintenanceWorkOrder.scheduled_date.asc().nullslast(), MaintenanceWorkOrder.created_at.desc())
        .all()
    )


def _order_row(order: MaintenanceWorkOrder) -> dict:
    vehicle = order.vehicle
    profile = vehicle.equipment_profile if vehicle else None
    return {
        "order_number": order.order_number,
        "vehicle": vehicle.frota if vehicle else "Sem equipamento",
        "family": profile.family.code if profile and profile.family else "SEM_FAMILIA",
        "title": order.title or order.item_name or "Serviço de manutenção",
        "status": order.status,
        "scheduled_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
        "assigned_mechanic": order.assigned_mechanic.nome if order.assigned_mechanic else "Sem responsável",
        "overdue": bool(order.status in OPEN_ORDER_STATUSES and order.scheduled_date and order.scheduled_date < today_manaus()),
    }


def _schedule_rows(filters: DashboardFilters, vehicle_ids: list[int]) -> tuple[dict, list[dict]]:
    if not vehicle_ids:
        return {"programmed": 0, "executed": 0, "not_executed": 0, "rescheduled": 0}, []
    rows = (
        MaintenanceScheduleItem.query
        .filter(
            MaintenanceScheduleItem.vehicle_id.in_(vehicle_ids),
            MaintenanceScheduleItem.scheduled_date >= filters.date_from,
            MaintenanceScheduleItem.scheduled_date <= filters.date_to,
            MaintenanceScheduleItem.status != "CANCELADO",
        )
        .order_by(MaintenanceScheduleItem.scheduled_date.asc(), MaintenanceScheduleItem.id.asc())
        .all()
    )
    counts = Counter(item.status for item in rows)
    summary = {
        "programmed": len(rows),
        "executed": int(counts.get("INSTALADO", 0)),
        "not_executed": int(counts.get("NAO_EXECUTADO", 0)),
        "rescheduled": int(counts.get("REPROGRAMADO", 0)),
    }
    items = []
    for item in rows[:12]:
        vehicle = item.vehicle
        items.append({
            "activity": (item.activity.titulo if item.activity else None) or (item.schedule.title if item.schedule else "Atividade"),
            "vehicle": vehicle.frota if vehicle else "Sem equipamento",
            "status": item.status,
            "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
        })
    return summary, items


def _preventive_summary(vehicle_ids: list[int]) -> tuple[dict, list[dict]]:
    if not vehicle_ids:
        return {"total": 0, "due": 0, "overdue": 0}, []
    plans = PreventivePlan.query.filter(
        PreventivePlan.status == "ATIVO",
        PreventivePlan.vehicle_id.in_(vehicle_ids),
    ).all()
    counts = Counter()
    items = []
    for plan in plans:
        due = plan_due_state(plan)
        status = due.get("status") or due.get("calculation_status") or "SEM_DADOS"
        counts[status] += 1
        if due.get("due") or due.get("overdue"):
            items.append({
                "code": plan.code,
                "vehicle": plan.vehicle.frota if plan.vehicle else "Sem equipamento",
                "title": plan.title,
                "status": status,
                "next_due_date": plan.next_due_date.isoformat() if plan.next_due_date else None,
                "priority": plan.priority,
            })
    summary = {
        "total": len(plans),
        "due": sum(value for key, value in counts.items() if key in {"VENCENDO", "VENCIDA", "CRITICA", "PROXIMA", "ATENCAO"}),
        "overdue": int(counts.get("VENCIDA", 0)),
    }
    return summary, items[:12]


def _materials_summary(vehicle_ids: list[int]) -> tuple[int, list[dict]]:
    if not vehicle_ids:
        return 0, []
    rows = (
        MaintenanceMaterial.query
        .join(MaintenanceSchedule, MaintenanceMaterial.schedule_id == MaintenanceSchedule.id)
        .join(MaintenanceWorkOrder, MaintenanceWorkOrder.schedule_id == MaintenanceSchedule.id)
        .filter(
            MaintenanceMaterial.status.in_({"AGUARDANDO_MATERIAL", "EM_COMPRAS"}),
            MaintenanceWorkOrder.vehicle_id.in_(vehicle_ids),
        )
        .all()
    )
    requests = {
        request.maintenance_material_id: request
        for request in PurchaseRequest.query.filter(
            PurchaseRequest.maintenance_material_id.in_([row.id for row in rows])
        ).all()
    } if rows else {}
    items = []
    seen_ids = set()
    for row in rows:
        if row.id in seen_ids:
            continue
        seen_ids.add(row.id)
        material = row.material
        request = requests.get(row.id)
        items.append({
            "reference": material.referencia if material else "Sem referência",
            "description": material.descricao if material else "Material não identificado",
            "status": row.status,
            "vehicle": row.schedule.work_orders[0].vehicle.frota if row.schedule and row.schedule.work_orders else "Sem equipamento",
            "expected_date": request.expected_date.isoformat() if request and request.expected_date else None,
            "supplier": request.supplier.name if request and request.supplier else None,
        })
    return len(items), items[:10]


def _backlog_summary(vehicle_ids: list[int]) -> tuple[dict, list[dict]]:
    filtered = [item for item in build_backlog() if (item.get("work_order") or {}).get("vehicle_id") in vehicle_ids]
    estimated_minutes = sum(int(item.get("estimated_duration_minutes") or 0) for item in filtered)
    summary = {
        "total": len(filtered),
        "overdue": sum(1 for item in filtered if item.get("overdue")),
        "estimated_minutes": estimated_minutes,
    }
    items = [{
        "order_number": (item.get("work_order") or {}).get("order_number"),
        "vehicle": ((item.get("work_order") or {}).get("vehicle") or {}).get("frota", "Sem equipamento"),
        "priority": item.get("priority") or "MEDIA",
        "age_days": item.get("age_days") or 0,
        "status": ((item.get("work_order") or {}).get("status") or "ABERTA"),
    } for item in filtered[:10]]
    return summary, items


def _critical_items(vehicles: list[Vehicle], orders: list[MaintenanceWorkOrder], preventives: list[dict]) -> list[dict]:
    order_by_vehicle = {order.vehicle_id: order for order in orders if order.status in OPEN_ORDER_STATUSES}
    preventive_by_vehicle = {item.get("vehicle"): item for item in preventives}
    items = []
    for vehicle in vehicles:
        summary = _vehicle_summary(vehicle)
        if summary["status"] not in {"INDISPONIVEL", "MANUTENCAO"} and vehicle.frota not in preventive_by_vehicle:
            continue
        order = order_by_vehicle.get(vehicle.id)
        items.append({
            "vehicle": summary["frota"],
            "family": summary["family"],
            "status": summary["status"],
            "reason": summary["status_reason"] or (order.title if order else "Preventiva pendente"),
            "forecast": order.scheduled_date.isoformat() if order and order.scheduled_date else None,
            "criticality": summary["criticality"],
        })
    priority = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAIXA": 3}
    return sorted(items, key=lambda item: (priority.get(item["criticality"], 9), item["vehicle"]))[:10]


def build_maintenance_tv_payload(filters: DashboardFilters) -> dict:
    cache_key = _cache_key(filters)
    now = monotonic()
    cached = _payload_cache.get(cache_key)
    if cached and now - cached[0] < TV_CACHE_TTL_SECONDS:
        payload = dict(cached[1])
        payload["performance"] = {"cached": True, "cache_ttl_seconds": TV_CACHE_TTL_SECONDS}
        return payload

    started_at = monotonic()
    vehicles = _scoped_vehicles(filters)
    vehicle_ids = [vehicle.id for vehicle in vehicles]
    summaries = [_vehicle_summary(vehicle) for vehicle in vehicles]
    statuses = Counter(item["status"] for item in summaries)
    available = int(statuses.get("DISPONIVEL", 0)) + int(statuses.get("RESTRICAO", 0))
    orders = _open_orders(vehicle_ids)
    open_orders = [order for order in orders if order.status in OPEN_ORDER_STATUSES]
    overdue_orders = [order for order in open_orders if order.scheduled_date and order.scheduled_date < today_manaus()]
    blocked_orders = [order for order in orders if order.status == "AGUARDANDO_MATERIAL"]
    schedule_summary, schedule_items = _schedule_rows(filters, vehicle_ids)
    preventive_summary, preventive_items = _preventive_summary(vehicle_ids)
    backlog_summary, backlog_items = _backlog_summary(vehicle_ids)
    blocked_materials, material_items = _materials_summary(vehicle_ids)
    reliability = _reliability_metrics(filters, vehicle_ids)
    critical_items = _critical_items(vehicles, orders, preventive_items)
    total = len(vehicles)
    availability = round((available / total) * 100, 2) if total else None
    payload = {
        "generated_at": now_manaus_naive().isoformat(),
        "filters": filters.to_dict(),
        "scope": {"families": [code.upper() for code in TV_FAMILY_CODES], "equipment_total": total},
        "kpis": {
            "equipment_total": total,
            "equipment_available": available,
            "equipment_unavailable": int(statuses.get("INDISPONIVEL", 0)),
            "equipment_in_maintenance": int(statuses.get("MANUTENCAO", 0)),
            "equipment_without_forecast": sum(1 for item in critical_items if not item.get("forecast")),
            "availability_percentage": availability,
            "work_orders": {
                "open": len(open_orders),
                "overdue": len(overdue_orders),
                "in_execution": sum(1 for order in open_orders if order.status == "EM_EXECUCAO"),
                "blocked_by_material": len(blocked_orders),
                "completed_in_period": sum(1 for order in orders if order.status == "CONCLUIDA" and order.updated_at and filters.date_from <= order.updated_at.date() <= filters.date_to),
            },
            "schedule": schedule_summary,
            "preventives": preventive_summary,
            "backlog": backlog_summary,
            "materials_blocked": blocked_materials,
            "critical_equipment": len(critical_items),
            "action_plans_overdue": 0,
            "decisions_open": 0,
            "reliability": {"mttr_hours": reliability.get("mttr_hours"), "mtbf_hours": reliability.get("mtbf_hours")},
        },
        "operational_status": [{"status": status, "total": count} for status, count in sorted(statuses.items())],
        "current_maintenance": [row for row in (_order_row(order) for order in open_orders if order.status == "EM_EXECUCAO")][:10],
        "schedule": schedule_items,
        "work_orders": [_order_row(order) for order in open_orders[:12]],
        "preventives": preventive_items,
        "backlog": backlog_items,
        "materials": material_items,
        "critical_equipment": critical_items,
        "action_plans": {"available": False, "items": []},
        "data_availability": {"action_plans": False, "message": "Planos de ação ainda não possuem cadastro próprio no banco."},
        "performance": {"cached": False, "cache_ttl_seconds": TV_CACHE_TTL_SECONDS, "query_duration_ms": round((monotonic() - started_at) * 1000, 2)},
    }
    _payload_cache[cache_key] = (now, payload)
    return payload
