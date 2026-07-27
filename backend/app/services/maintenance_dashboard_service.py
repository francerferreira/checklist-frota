from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from time import monotonic

from app.models import (
    EmergencyEvent,
    EquipmentFamily,
    EquipmentProfile,
    EquipmentStatusEvent,
    MaintenanceSchedule,
    MaintenanceWorkOrder,
    MaintenanceWorkOrderCost,
    OperationalLocation,
    PreventiveExecution,
    PreventivePlan,
    Vehicle,
    WorkOrderExecution,
)
from app.services.availability_service import build_availability_overview
from app.services.pcm_service import build_backlog, plan_due_state
from app.utils.timezone import now_manaus_naive, today_manaus


OPEN_ORDER_STATUSES = {"ABERTA", "PROGRAMADA", "AGUARDANDO_MATERIAL", "EM_EXECUCAO", "REPROGRAMADA"}
CRITICAL_OPERATIONAL_STATUSES = {"INDISPONIVEL", "MANUTENCAO"}
CRITICALITY_ORDER = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAIXA": 3}
DASHBOARD_CHART_CACHE_TTL_SECONDS = 15
_dashboard_chart_cache: dict[tuple, tuple[float, dict]] = {}


@dataclass(frozen=True)
class DashboardFilters:
    date_from: date
    date_to: date
    family_id: int | None = None
    vehicle_id: int | None = None
    location_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "family_id": self.family_id,
            "vehicle_id": self.vehicle_id,
            "location_id": self.location_id,
        }


def _parse_positive_int(value, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalido.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} invalido.")
    return parsed


def _parse_date(value, default: date, field_name: str) -> date:
    if value in (None, ""):
        return default
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalida; use AAAA-MM-DD.") from exc


def parse_dashboard_filters(args) -> DashboardFilters:
    today = today_manaus()
    default_start = today.replace(day=1)
    date_from = _parse_date(args.get("data_inicial"), default_start, "Data inicial")
    date_to = _parse_date(args.get("data_final"), today, "Data final")
    if date_to < date_from:
        raise ValueError("A data final deve ser igual ou posterior a data inicial.")
    return DashboardFilters(
        date_from=date_from,
        date_to=date_to,
        family_id=_parse_positive_int(args.get("familia_id"), "Familia"),
        vehicle_id=_parse_positive_int(args.get("veiculo_id"), "Equipamento"),
        location_id=_parse_positive_int(args.get("local_id"), "Local"),
    )


def _vehicle_ids(filters: DashboardFilters) -> list[int]:
    query = Vehicle.query.filter(Vehicle.ativo.is_(True)).join(Vehicle.equipment_profile)
    if filters.family_id:
        query = query.filter(EquipmentProfile.family_id == filters.family_id)
    if filters.location_id:
        query = query.filter(EquipmentProfile.operational_location_id == filters.location_id)
    if filters.vehicle_id:
        query = query.filter(Vehicle.id == filters.vehicle_id)
    return [row[0] for row in query.with_entities(Vehicle.id).all()]


def _window_bounds(filters: DashboardFilters) -> tuple[datetime, datetime]:
    start = datetime.combine(filters.date_from, time.min)
    end = min(datetime.combine(filters.date_to, time.max), now_manaus_naive())
    return start, end


def _filtered_availability(filters: DashboardFilters) -> dict:
    return build_availability_overview(
        date_from=filters.date_from.isoformat(),
        date_to=filters.date_to.isoformat(),
        family_id=filters.family_id,
        location_id=filters.location_id,
        vehicle_id=filters.vehicle_id,
    )


def _availability_by_family(rows: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in rows:
        family = row.get("family") or {}
        key = str(family.get("code") or "sem_familia")
        group = groups.setdefault(
            key,
            {
                "family_id": family.get("id"),
                "family_code": key,
                "family_name": family.get("name") or "Sem familia",
                "total": 0,
                "available": 0,
                "unavailable": 0,
                "maintenance": 0,
                "measured": [],
            },
        )
        group["total"] += 1
        status = ((row.get("vehicle") or {}).get("operational_state") or {}).get("operational_status")
        if status in {"DISPONIVEL", "RESTRICAO"}:
            group["available"] += 1
        if status == "INDISPONIVEL":
            group["unavailable"] += 1
        if status == "MANUTENCAO":
            group["maintenance"] += 1
        availability = row.get("availability_percentage")
        if isinstance(availability, (int, float)):
            group["measured"].append(availability)
    result = []
    for group in groups.values():
        measured = group.pop("measured")
        group["availability_percentage"] = round(sum(measured) / len(measured), 2) if measured else None
        group["measured_equipment"] = len(measured)
        result.append(group)
    return sorted(result, key=lambda item: item["family_name"])


def _orders_for_vehicles(vehicle_ids: list[int]) -> list[MaintenanceWorkOrder]:
    if not vehicle_ids:
        return []
    return (
        MaintenanceWorkOrder.query
        .filter(MaintenanceWorkOrder.vehicle_id.in_(vehicle_ids))
        .order_by(MaintenanceWorkOrder.created_at.desc())
        .all()
    )


def _work_order_completion_at(order: MaintenanceWorkOrder) -> datetime | None:
    execution = order.execution
    if execution and execution.released_at:
        return execution.released_at
    return order.updated_at if order.status == "CONCLUIDA" else None


def _work_order_summary(filters: DashboardFilters, vehicle_ids: list[int]) -> dict:
    today = today_manaus()
    rows = _orders_for_vehicles(vehicle_ids)
    open_rows = [row for row in rows if row.status in OPEN_ORDER_STATUSES]
    overdue_rows = [row for row in open_rows if row.scheduled_date and row.scheduled_date < today]
    blocked_rows = [row for row in rows if row.status == "AGUARDANDO_MATERIAL"]
    completed_rows = [
        row for row in rows
        if (completed_at := _work_order_completion_at(row))
        and filters.date_from <= completed_at.date() <= filters.date_to
    ]
    source_counts = Counter(
        row.schedule.source_origin_type() if row.schedule else "SEM_ORIGEM"
        for row in rows
    )
    return {
        "open": len(open_rows),
        "overdue": len(overdue_rows),
        "blocked_by_material": len(blocked_rows),
        "completed_in_period": len(completed_rows),
        "by_source": [
            {"source": source, "total": total}
            for source, total in sorted(source_counts.items())
        ],
    }


def _reliability_metrics(filters: DashboardFilters, vehicle_ids: list[int]) -> dict:
    if not vehicle_ids:
        return {"mtbf_hours": None, "mttr_hours": None, "comparable_failures": 0, "completed_repairs": 0}
    window_start, window_end = _window_bounds(filters)
    executions = (
        WorkOrderExecution.query
        .join(MaintenanceWorkOrder)
        .filter(
            MaintenanceWorkOrder.vehicle_id.in_(vehicle_ids),
            WorkOrderExecution.failure_started_at >= window_start,
            WorkOrderExecution.failure_started_at <= window_end,
            WorkOrderExecution.repair_started_at.isnot(None),
            WorkOrderExecution.released_at.isnot(None),
        )
        .order_by(MaintenanceWorkOrder.vehicle_id.asc(), WorkOrderExecution.failure_started_at.asc())
        .all()
    )
    repair_hours: list[float] = []
    failure_intervals: list[float] = []
    previous_release_by_vehicle: dict[int, datetime] = {}
    for execution in executions:
        order = execution.work_order
        if not order or execution.released_at < execution.repair_started_at:
            continue
        repair_hours.append((execution.released_at - execution.repair_started_at).total_seconds() / 3600)
        previous_release = previous_release_by_vehicle.get(order.vehicle_id)
        if previous_release and execution.failure_started_at >= previous_release:
            failure_intervals.append((execution.failure_started_at - previous_release).total_seconds() / 3600)
        previous_release_by_vehicle[order.vehicle_id] = execution.released_at
    return {
        "mtbf_hours": round(sum(failure_intervals) / len(failure_intervals), 2) if failure_intervals else None,
        "mttr_hours": round(sum(repair_hours) / len(repair_hours), 2) if repair_hours else None,
        "comparable_failures": len(failure_intervals),
        "completed_repairs": len(repair_hours),
    }


def _governance_metrics(filters: DashboardFilters, vehicle_ids: list[int]) -> dict:
    if not vehicle_ids:
        return {
            "cost_total": 0.0,
            "cost_records": 0,
            "cost_by_category": {},
            "classified_orders": 0,
            "orders_with_shift": 0,
        }
    window_start, window_end = _window_bounds(filters)
    costs = (
        MaintenanceWorkOrderCost.query
        .join(MaintenanceWorkOrder)
        .filter(
            MaintenanceWorkOrder.vehicle_id.in_(vehicle_ids),
            MaintenanceWorkOrderCost.occurred_at >= window_start,
            MaintenanceWorkOrderCost.occurred_at <= window_end,
        )
        .all()
    )
    totals = Counter()
    for cost in costs:
        totals[cost.category] += float(cost.amount or 0)
    orders = [
        order
        for order in _orders_for_vehicles(vehicle_ids)
        if order.created_at and filters.date_from <= order.created_at.date() <= filters.date_to
    ]
    classified_orders = sum(1 for order in orders if order.failure_cause or order.affected_component)
    orders_with_shift = sum(1 for order in orders if order.work_shift)
    return {
        "cost_total": round(sum(totals.values()), 2),
        "cost_records": len(costs),
        "cost_by_category": {category: round(total, 2) for category, total in totals.items()},
        "classified_orders": classified_orders,
        "orders_with_shift": orders_with_shift,
    }


def _due_preventives(filters: DashboardFilters, vehicle_ids: list[int]) -> list[dict]:
    if not vehicle_ids:
        return []
    rows = PreventivePlan.query.filter(
        PreventivePlan.status == "ATIVO",
        PreventivePlan.vehicle_id.in_(vehicle_ids),
    ).all()
    return [plan.to_dict(plan_due_state(plan)) for plan in rows if plan_due_state(plan).get("due")]


def build_dashboard_filter_options() -> dict:
    families = (
        EquipmentFamily.query
        .join(EquipmentFamily.profiles)
        .join(EquipmentProfile.vehicle)
        .filter(EquipmentFamily.active.is_(True))
        .filter(Vehicle.ativo.is_(True))
        .distinct()
        .order_by(EquipmentFamily.name.asc())
        .all()
    )
    locations = (
        OperationalLocation.query
        .join(OperationalLocation.profiles)
        .join(EquipmentProfile.vehicle)
        .filter(OperationalLocation.active.is_(True))
        .filter(Vehicle.ativo.is_(True))
        .distinct()
        .order_by(OperationalLocation.name.asc())
        .all()
    )
    vehicles = (
        Vehicle.query
        .filter(Vehicle.ativo.is_(True))
        .join(Vehicle.equipment_profile)
        .order_by(Vehicle.frota.asc())
        .all()
    )
    return {
        "families": [item.to_dict() for item in families],
        "locations": [item.to_dict() for item in locations],
        "vehicles": [
            {
                "id": item.id,
                "frota": item.frota,
                "modelo": item.modelo,
                "family_id": item.equipment_profile.family_id,
                "location_id": item.equipment_profile.operational_location_id,
            }
            for item in vehicles
        ],
        "supported_filters": ["data_inicial", "data_final", "familia_id", "veiculo_id", "local_id"],
    }


def build_dashboard_summary(filters: DashboardFilters) -> dict:
    vehicle_ids = _vehicle_ids(filters)
    availability = _filtered_availability(filters)
    summary = availability.get("summary") or {}
    status_counts = summary.get("status_counts") or {}
    due_preventives = _due_preventives(filters, vehicle_ids)
    governance = _governance_metrics(filters, vehicle_ids)
    unavailable = []
    if not governance["cost_records"]:
        unavailable.append("custos")
    if not governance["classified_orders"]:
        unavailable.append("causa e componente de falha")
    if not governance["orders_with_shift"]:
        unavailable.append("turno")
    return {
        "filters": filters.to_dict(),
        "generated_at": now_manaus_naive().isoformat(),
        "kpis": {
            "equipment_total": summary.get("total", 0),
            "equipment_available": int(status_counts.get("DISPONIVEL", 0)) + int(status_counts.get("RESTRICAO", 0)),
            "equipment_unavailable": int(status_counts.get("INDISPONIVEL", 0)),
            "equipment_in_maintenance": int(status_counts.get("MANUTENCAO", 0)),
            "equipment_unreported": int(status_counts.get("SEM_APONTAMENTO", 0)),
            "availability_percentage": summary.get("average_availability_percentage"),
            "availability_measured_equipment": summary.get("measured_equipment", 0),
            "work_orders": _work_order_summary(filters, vehicle_ids),
            "preventives_due_or_overdue": len(due_preventives),
            "reliability": _reliability_metrics(filters, vehicle_ids),
            "governance": governance,
        },
        "data_availability": {
            "maintenance_costs": bool(governance["cost_records"]),
            "failure_cause": bool(governance["classified_orders"]),
            "work_shift": bool(governance["orders_with_shift"]),
            "reason": (
                "Todos os campos de governanca possuem apontamentos no filtro."
                if not unavailable
                else "Ainda faltam apontamentos reais de " + ", ".join(unavailable) + " no filtro."
            ),
        },
    }


def build_dashboard_availability(filters: DashboardFilters) -> dict:
    overview = _filtered_availability(filters)
    return {
        "filters": filters.to_dict(),
        "period": overview.get("period"),
        "summary": overview.get("summary"),
        "by_family": _availability_by_family(overview.get("rows") or []),
        "by_equipment": overview.get("rows") or [],
    }


def build_dashboard_work_orders(filters: DashboardFilters, *, page: int = 1, page_size: int = 50) -> dict:
    if page <= 0 or page_size <= 0 or page_size > 100:
        raise ValueError("Paginacao invalida.")
    vehicle_ids = _vehicle_ids(filters)
    today = today_manaus()
    rows = _orders_for_vehicles(vehicle_ids)
    offset = (page - 1) * page_size
    items = []
    for order in rows[offset:offset + page_size]:
        vehicle = order.vehicle
        profile = vehicle.equipment_profile if vehicle else None
        scheduled_date = order.scheduled_date
        age_days = max((today - scheduled_date).days, 0) if scheduled_date else None
        items.append({
            "id": order.id,
            "order_number": order.order_number,
            "vehicle": {"id": vehicle.id, "frota": vehicle.frota} if vehicle else None,
            "family": profile.family.to_dict() if profile and profile.family else None,
            "location": profile.location.to_dict() if profile and profile.location else None,
            "title": order.title,
            "item_name": order.item_name,
            "source": order.schedule.source_origin_type() if order.schedule else None,
            "status": order.status,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "age_days": age_days,
            "overdue": bool(order.status in OPEN_ORDER_STATUSES and scheduled_date and scheduled_date < today),
            "assigned_mechanic": order.assigned_mechanic.to_dict() if order.assigned_mechanic else None,
        })
    return {"filters": filters.to_dict(), "page": page, "page_size": page_size, "total": len(rows), "items": items}


def build_dashboard_preventives(filters: DashboardFilters) -> dict:
    vehicle_ids = _vehicle_ids(filters)
    plans = PreventivePlan.query.filter(
        PreventivePlan.status == "ATIVO",
        PreventivePlan.vehicle_id.in_(vehicle_ids),
    ).all() if vehicle_ids else []
    items = []
    for plan in plans:
        item = plan.to_dict(plan_due_state(plan))
        execution = (
            PreventiveExecution.query
            .filter(
                PreventiveExecution.preventive_plan_id == plan.id,
                PreventiveExecution.status.in_(("PLANEJADA", "PROGRAMADA", "EM_EXECUCAO")),
            )
            .order_by(PreventiveExecution.created_at.desc(), PreventiveExecution.id.desc())
            .first()
        )
        item["execution"] = execution.to_dict() if execution else None
        items.append(item)
    priority_order = {"VENCIDA": 0, "CRITICA": 1, "PROXIMA": 2, "ATENCAO": 3, "NO_PRAZO": 4, "SEM_DADOS": 5}
    items.sort(key=lambda item: (
        priority_order.get((item.get("due") or {}).get("calculation_status"), 9),
        item.get("next_due_date") or "9999-12-31",
        item.get("vehicle", {}).get("frota", "") if item.get("vehicle") else "",
    ))
    summary = {status: 0 for status in ("NO_PRAZO", "ATENCAO", "PROXIMA", "CRITICA", "VENCIDA", "SEM_DADOS")}
    for item in items:
        status = (item.get("due") or {}).get("calculation_status") or "SEM_DADOS"
        summary[status] = summary.get(status, 0) + 1
    return {
        "filters": filters.to_dict(),
        "total_plans": len(items),
        "total_due_or_overdue": sum(1 for item in items if (item.get("due") or {}).get("due") or (item.get("due") or {}).get("overdue")),
        "summary": summary,
        "items": items,
    }


def _dashboard_chart_cache_key(filters: DashboardFilters) -> tuple:
    return (
        filters.date_from.isoformat(),
        filters.date_to.isoformat(),
        filters.family_id,
        filters.vehicle_id,
        filters.location_id,
    )


def _operational_event_charts(filters: DashboardFilters, vehicle_ids: list[int]) -> dict:
    if not vehicle_ids:
        return {"trend": [], "unavailability_reasons": []}
    window_start, window_end = _window_bounds(filters)
    events = (
        EquipmentStatusEvent.query
        .with_entities(
            EquipmentStatusEvent.started_at,
            EquipmentStatusEvent.status,
            EquipmentStatusEvent.reason,
        )
        .filter(
            EquipmentStatusEvent.vehicle_id.in_(vehicle_ids),
            EquipmentStatusEvent.started_at >= window_start,
            EquipmentStatusEvent.started_at <= window_end,
        )
        .order_by(EquipmentStatusEvent.started_at.asc())
        .all()
    )
    daily_counts: dict[str, Counter] = defaultdict(Counter)
    reason_counts: Counter = Counter()
    for started_at, status, reason in events:
        daily_counts[started_at.date().isoformat()][status] += 1
        if status == "INDISPONIVEL" and reason and reason.strip():
            reason_counts[reason.strip()] += 1
    trend = []
    for day, counts in sorted(daily_counts.items()):
        trend.append({
            "date": day,
            "total": sum(counts.values()),
            "available": counts.get("DISPONIVEL", 0),
            "unavailable": counts.get("INDISPONIVEL", 0),
            "restricted": counts.get("RESTRICAO", 0),
            "maintenance": counts.get("MANUTENCAO", 0),
        })
    return {
        "trend": trend,
        "unavailability_reasons": [
            {"reason": reason, "total": total}
            for reason, total in reason_counts.most_common(8)
        ],
    }


def _preventive_status_chart(vehicle_ids: list[int]) -> list[dict]:
    if not vehicle_ids:
        return []
    counts = Counter()
    for plan in PreventivePlan.query.filter(
        PreventivePlan.status == "ATIVO",
        PreventivePlan.vehicle_id.in_(vehicle_ids),
    ).all():
        counts[plan_due_state(plan).get("status", "SEM_DADOS")] += 1
    order = ("VENCIDA", "VENCENDO", "EM_DIA")
    return [{"status": status, "total": counts[status]} for status in order if counts[status]]


def build_dashboard_charts(filters: DashboardFilters) -> dict:
    cache_key = _dashboard_chart_cache_key(filters)
    cache_now = monotonic()
    expired_keys = [
        key for key, (stored_at, _) in _dashboard_chart_cache.items()
        if cache_now - stored_at >= DASHBOARD_CHART_CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        del _dashboard_chart_cache[key]
    cached = _dashboard_chart_cache.get(cache_key)
    if cached and cache_now - cached[0] < DASHBOARD_CHART_CACHE_TTL_SECONDS:
        payload = dict(cached[1])
        payload["performance"] = {
            "cached": True,
            "cache_ttl_seconds": DASHBOARD_CHART_CACHE_TTL_SECONDS,
            "query_duration_ms": 0,
        }
        return payload

    started_at = monotonic()
    vehicle_ids = _vehicle_ids(filters)
    overview = _filtered_availability(filters)
    status_counts = (overview.get("summary") or {}).get("status_counts") or {}
    work_order_counts = Counter(order.status for order in _orders_for_vehicles(vehicle_ids))
    events = _operational_event_charts(filters, vehicle_ids)
    payload = {
        "filters": filters.to_dict(),
        "availability_summary": overview.get("summary") or {},
        "availability_by_family": _availability_by_family(overview.get("rows") or []),
        "operational_status": [
            {"status": status, "total": int(status_counts.get(status, 0))}
            for status in ("DISPONIVEL", "INDISPONIVEL", "RESTRICAO", "MANUTENCAO", "SEM_APONTAMENTO")
            if int(status_counts.get(status, 0))
        ],
        "work_orders_by_status": [
            {"status": status, "total": total}
            for status, total in sorted(work_order_counts.items())
        ],
        "preventives_by_status": _preventive_status_chart(vehicle_ids),
        "operational_events_trend": events["trend"],
        "unavailability_reasons": events["unavailability_reasons"],
    }
    query_duration_ms = round((monotonic() - started_at) * 1000, 2)
    _dashboard_chart_cache[cache_key] = (cache_now, payload)
    payload["performance"] = {
        "cached": False,
        "cache_ttl_seconds": DASHBOARD_CHART_CACHE_TTL_SECONDS,
        "query_duration_ms": query_duration_ms,
    }
    return payload


def build_dashboard_critical_equipment(filters: DashboardFilters) -> dict:
    vehicle_ids = _vehicle_ids(filters)
    availability = _filtered_availability(filters)
    by_vehicle = {row["vehicle"]["id"]: row for row in availability.get("rows") or []}
    backlog_by_vehicle: dict[int, list[dict]] = defaultdict(list)
    for item in build_backlog():
        order = item.get("work_order") or {}
        if order.get("vehicle_id") in vehicle_ids:
            backlog_by_vehicle[order["vehicle_id"]].append(item)
    due_by_vehicle: dict[int, list[dict]] = defaultdict(list)
    for plan in _due_preventives(filters, vehicle_ids):
        due_by_vehicle[plan["vehicle_id"]].append(plan)
    emergency_by_vehicle: dict[int, list[EmergencyEvent]] = defaultdict(list)
    if vehicle_ids:
        for emergency in EmergencyEvent.query.filter(
            EmergencyEvent.vehicle_id.in_(vehicle_ids),
            EmergencyEvent.status.in_({"ABERTA", "TRIAGEM", "CONVERTIDA"}),
        ).all():
            emergency_by_vehicle[emergency.vehicle_id].append(emergency)

    items = []
    for vehicle_id in vehicle_ids:
        row = by_vehicle.get(vehicle_id)
        if not row:
            continue
        vehicle = row["vehicle"]
        state = vehicle.get("operational_state") or {}
        reasons = []
        status = state.get("operational_status")
        if status in CRITICAL_OPERATIONAL_STATUSES:
            reasons.append("STATUS_OPERACIONAL")
        if due_by_vehicle.get(vehicle_id):
            reasons.append("PREVENTIVA_VENCENDO_OU_VENCIDA")
        if backlog_by_vehicle.get(vehicle_id):
            reasons.append("OS_EM_ABERTO")
        if emergency_by_vehicle.get(vehicle_id):
            reasons.append("EMERGENCIAL_ABERTA")
        if not reasons:
            continue
        profile = vehicle.get("family") or {}
        criticality = vehicle.get("criticality") or "MEDIA"
        items.append({
            "vehicle": vehicle,
            "family": profile,
            "location": vehicle.get("operational_location"),
            "operational_status": status,
            "status_reason": state.get("status_reason"),
            "stopped_since": state.get("status_updated_at"),
            "availability_percentage": row.get("availability_percentage"),
            "criticality": criticality,
            "reasons": reasons,
            "open_work_orders": backlog_by_vehicle.get(vehicle_id, []),
            "due_preventives": due_by_vehicle.get(vehicle_id, []),
            "open_emergencies": [event.to_dict() for event in emergency_by_vehicle.get(vehicle_id, [])],
        })
    items.sort(key=lambda item: (CRITICALITY_ORDER.get(item["criticality"], 9), -len(item["reasons"]), item["vehicle"].get("frota") or ""))
    return {"filters": filters.to_dict(), "total": len(items), "items": items}
