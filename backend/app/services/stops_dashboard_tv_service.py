from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import monotonic

from app.models import EquipmentProfile, EquipmentStatusEvent, EquipmentFamily, Vehicle
from app.services.maintenance_dashboard_service import DashboardFilters
from app.utils.timezone import now_manaus_naive


STOP_FAMILY_CODES = ("lbs", "rtg")
STOP_STATUSES = ("INDISPONIVEL", "MANUTENCAO")
STOP_TARGETS_PATH = Path(__file__).resolve().parents[2] / "stop_dashboard_targets.json"
STOP_CACHE_TTL_SECONDS = 15
_payload_cache: dict[tuple, tuple[float, dict]] = {}


def _cache_key(filters: DashboardFilters) -> tuple:
    return (filters.date_from.isoformat(), filters.date_to.isoformat(), filters.family_id, filters.vehicle_id, filters.location_id)


def _period_bounds(filters: DashboardFilters) -> tuple[datetime, datetime]:
    start = datetime.combine(filters.date_from, time.min)
    end = min(datetime.combine(filters.date_to, time.max), now_manaus_naive())
    return start, end


def _load_targets(period: date) -> dict[str, float]:
    try:
        payload = json.loads(STOP_TARGETS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    selected = payload.get("monthly", {}).get(period.strftime("%Y-%m")) or payload.get("default") or {}
    return {str(key): float(value) for key, value in selected.items() if isinstance(value, (int, float)) and value >= 0}


def _area_code(vehicle: Vehicle) -> str:
    profile = vehicle.equipment_profile
    family = (profile.family.code if profile and profile.family else vehicle.tipo or "").strip().lower()
    location = " ".join(filter(None, [profile.location.full_name() if profile and profile.location else None, vehicle.local])).lower()
    if family == "lbs":
        return "lbs-pier"
    if "alfand" in location:
        return "rtg-alfandegado"
    if "atr" in location:
        return "rtg-atr"
    return "rtg-outros" if family == "rtg" else "sem-area"


def _family_code(vehicle: Vehicle) -> str:
    profile = vehicle.equipment_profile
    return (profile.family.code if profile and profile.family else vehicle.tipo or "").strip().lower()


def _area_label(code: str) -> str:
    return {
        "lbs-pier": "LBS · PÍER",
        "rtg-atr": "RTG · ATR",
        "rtg-alfandegado": "RTG · ALFANDEGADO",
        "rtg-total": "RTG · CONSOLIDADO",
        "rtg-outros": "RTG · SEM ÁREA",
    }.get(code, "SEM ÁREA")


def _hours_label(hours: float | int | None) -> str:
    if hours is None:
        return "SEM DADOS"
    total_minutes = max(0, round(float(hours) * 60))
    return f"{total_minutes // 60}h {total_minutes % 60:02d}min"


def _overlap_hours(started_at: datetime, ended_at: datetime | None, window_start: datetime, window_end: datetime) -> float:
    start = max(started_at, window_start)
    end = min(ended_at or window_end, window_end)
    seconds = max(0, (end - start).total_seconds())
    return round(seconds / 3600, 2)


def _vehicles(filters: DashboardFilters) -> list[Vehicle]:
    query = Vehicle.query.join(Vehicle.equipment_profile).join(EquipmentProfile.family).filter(
        Vehicle.ativo.is_(True),
        EquipmentFamily.code.in_(STOP_FAMILY_CODES),
    )
    if filters.family_id:
        query = query.filter(EquipmentProfile.family_id == filters.family_id)
    if filters.vehicle_id:
        query = query.filter(Vehicle.id == filters.vehicle_id)
    if filters.location_id:
        query = query.filter(EquipmentProfile.operational_location_id == filters.location_id)
    return query.order_by(Vehicle.frota.asc()).all()


def _event_rows(vehicles: list[Vehicle], window_start: datetime, window_end: datetime) -> list[dict]:
    vehicle_ids = [vehicle.id for vehicle in vehicles]
    if not vehicle_ids:
        return []
    events = EquipmentStatusEvent.query.filter(
        EquipmentStatusEvent.vehicle_id.in_(vehicle_ids),
        EquipmentStatusEvent.status.in_(STOP_STATUSES),
        EquipmentStatusEvent.started_at < window_end,
        (EquipmentStatusEvent.ended_at.is_(None) | (EquipmentStatusEvent.ended_at >= window_start)),
    ).order_by(EquipmentStatusEvent.started_at.desc(), EquipmentStatusEvent.id.desc()).all()
    by_id = {vehicle.id: vehicle for vehicle in vehicles}
    rows = []
    for event in events:
        vehicle = by_id.get(event.vehicle_id)
        if not vehicle or not event.started_at:
            continue
        hours = _overlap_hours(event.started_at, event.ended_at, window_start, window_end)
        if hours <= 0:
            continue
        area = _area_code(vehicle)
        rows.append({
            "id": event.id,
            "vehicle_id": vehicle.id,
            "vehicle": vehicle.frota,
            "family": _family_code(vehicle).upper(),
            "area_code": area,
            "area": _area_label(area),
            "status": event.status,
            "reason": event.reason or "SEM MOTIVO INFORMADO",
            "started_at": event.started_at.isoformat(),
            "ended_at": event.ended_at.isoformat() if event.ended_at else None,
            "hours": hours,
            "duration": _hours_label(hours),
            "active": event.ended_at is None,
            "criticality": vehicle.equipment_profile.criticality if vehicle.equipment_profile else "MEDIA",
        })
    return rows


def _target_row(code: str, hours: float, targets: dict[str, float], rows: list[dict]) -> dict:
    goal = targets.get(code)
    percentage = round((hours / goal) * 100, 2) if goal and goal > 0 else None
    status = _status_for_percentage(percentage)
    return {
        "code": code,
        "label": _area_label(code),
        "hours": round(hours, 2),
        "goal_hours": goal,
        "percentage": percentage,
        "balance_hours": round(max(0, goal - hours), 2) if goal is not None else None,
        "stopped_equipment": len({row["vehicle_id"] for row in rows}),
        "status": status,
    }


def _status_for_percentage(percentage: float | None) -> str:
    if percentage is None:
        return "SEM_DADOS"
    if percentage > 100:
        return "CRITICO"
    if percentage > 90:
        return "VERMELHO"
    if percentage > 70:
        return "ATENCAO"
    return "NORMAL"


def _projection_row(
    code: str,
    current_hours: float,
    targets: dict[str, float],
    elapsed_days: int,
    period_days: int,
    has_data: bool,
) -> dict:
    goal = targets.get(code)
    projected = None
    if has_data and elapsed_days > 0:
        projected = round(current_hours / elapsed_days * period_days, 2)
    percentage = round((projected / goal) * 100, 2) if projected is not None and goal else None
    return {
        "code": code,
        "label": _area_label(code),
        "current_hours": round(current_hours, 2),
        "projected_hours": projected,
        "goal_hours": goal,
        "percentage": percentage,
        "status": _status_for_percentage(percentage),
        "elapsed_days": elapsed_days,
        "period_days": period_days,
    }


def _daily_slices(row: dict, window_start: datetime, window_end: datetime) -> list[tuple[str, float]]:
    started_at = datetime.fromisoformat(row["started_at"])
    ended_at = datetime.fromisoformat(row["ended_at"]) if row.get("ended_at") else window_end
    cursor = max(started_at, window_start)
    end = min(ended_at, window_end)
    slices: list[tuple[str, float]] = []
    while cursor < end:
        next_day = datetime.combine(cursor.date() + timedelta(days=1), time.min)
        slice_end = min(end, next_day)
        hours = (slice_end - cursor).total_seconds() / 3600
        if hours > 0:
            slices.append((cursor.date().isoformat(), round(hours, 2)))
        cursor = slice_end
    return slices


def build_stops_dashboard_tv_payload(filters: DashboardFilters) -> dict:
    cache_key = _cache_key(filters)
    now = monotonic()
    cached = _payload_cache.get(cache_key)
    if cached and now - cached[0] < STOP_CACHE_TTL_SECONDS:
        payload = dict(cached[1])
        payload["performance"] = {"cached": True, "cache_ttl_seconds": STOP_CACHE_TTL_SECONDS}
        return payload
    started = monotonic()
    window_start, window_end = _period_bounds(filters)
    vehicles = _vehicles(filters)
    rows = _event_rows(vehicles, window_start, window_end)
    active_rows = sorted((row for row in rows if row["active"]), key=lambda row: (-row["hours"], row["vehicle"]))
    targets = _load_targets(filters.date_to)
    by_area = defaultdict(float)
    for row in rows:
        by_area[row["area_code"]] += row["hours"]
    target_rows = {
        code: _target_row(code, by_area.get(code, 0), targets, [row for row in rows if row["area_code"] == code])
        for code in ("lbs-pier", "rtg-atr", "rtg-alfandegado", "rtg-total")
    }
    rtg_rows = [row for row in rows if row["area_code"] in {"rtg-atr", "rtg-alfandegado"}]
    rtg_total_hours = round(by_area.get("rtg-atr", 0) + by_area.get("rtg-alfandegado", 0), 2)
    target_rows["rtg-total"] = _target_row("rtg-total", rtg_total_hours, targets, rtg_rows)
    by_vehicle = defaultdict(lambda: {"hours": 0.0, "events": 0, "family": "", "area": "", "status": "", "reasons": Counter()})
    by_reason = defaultdict(lambda: {"hours": 0.0, "events": 0})
    daily = defaultdict(lambda: {"hours": 0.0, "lbs": 0.0, "rtg": 0.0})
    for row in rows:
        vehicle = by_vehicle[row["vehicle"]]
        vehicle.update({"family": row["family"], "area": row["area"], "status": row["status"]})
        vehicle["hours"] += row["hours"]
        vehicle["events"] += 1
        vehicle["reasons"][row["reason"]] += row["hours"]
        reason = by_reason[row["reason"]]
        reason["hours"] += row["hours"]
        reason["events"] += 1
        for day, hours in _daily_slices(row, window_start, window_end):
            daily[day]["hours"] += hours
            daily[day]["lbs" if row["family"] == "LBS" else "rtg"] += hours
    total_hours = round(sum(row["hours"] for row in rows), 2)
    offenders = []
    for vehicle, values in by_vehicle.items():
        principal_reason = values["reasons"].most_common(1)
        offenders.append({
            "vehicle": vehicle,
            "family": values["family"],
            "area": values["area"],
            "status": values["status"],
            "hours": round(values["hours"], 2),
            "events": values["events"],
            "average_hours": round(values["hours"] / values["events"], 2) if values["events"] else 0,
            "duration": _hours_label(values["hours"]),
            "principal_reason": principal_reason[0][0] if principal_reason else "SEM MOTIVO INFORMADO",
            "participation": round(values["hours"] / total_hours * 100, 2) if total_hours else None,
        })
    offenders = sorted(offenders, key=lambda item: (-item["hours"], item["vehicle"]))[:10]
    reasons = sorted(({
        "reason": reason,
        **values,
        "hours": round(values["hours"], 2),
        "participation": round(values["hours"] / total_hours * 100, 2) if total_hours else None,
    } for reason, values in by_reason.items()), key=lambda item: (-item["hours"], item["reason"]))[:8]
    daily_trend = [{"date": day, "hours": round(values["hours"], 2), "lbs_hours": round(values["lbs"], 2), "rtg_hours": round(values["rtg"], 2)} for day, values in sorted(daily.items())]
    monthly_summary = {
        "total_hours": total_hours,
        "total_events": len(rows),
        "average_hours": round(total_hours / len(rows), 2) if rows else None,
        "longest_hours": round(max((row["hours"] for row in rows), default=0), 2) if rows else None,
        "active_total": len(active_rows),
        "days_with_data": len(daily_trend),
    }
    month_start = date(filters.date_to.year, filters.date_to.month, 1)
    next_month = date(filters.date_to.year + (filters.date_to.month == 12), 1 if filters.date_to.month == 12 else filters.date_to.month + 1, 1)
    period_days = (next_month - month_start).days
    projection_start = max(filters.date_from, month_start)
    projection_end = min(filters.date_to, window_end.date())
    elapsed_days = max(0, (projection_end - projection_start).days + 1) if projection_end >= projection_start else 0
    area_hours = {
        "lbs-pier": by_area.get("lbs-pier", 0),
        "rtg-atr": by_area.get("rtg-atr", 0),
        "rtg-alfandegado": by_area.get("rtg-alfandegado", 0),
    }
    area_hours["rtg-total"] = area_hours["rtg-atr"] + area_hours["rtg-alfandegado"]
    projections = {
        code: _projection_row(
            code,
            area_hours[code],
            targets,
            elapsed_days,
            period_days,
            bool([row for row in rows if row["area_code"] == code] if code != "rtg-total" else rtg_rows),
        )
        for code in ("lbs-pier", "rtg-atr", "rtg-alfandegado", "rtg-total")
    }
    period_label = filters.date_to.strftime("%m/%Y")
    period_range = f"{filters.date_from.strftime('%d/%m/%Y')} a {filters.date_to.strftime('%d/%m/%Y')}"
    payload = {
        "generated_at": now_manaus_naive().isoformat(),
        "period": {"label": f"COMPETÊNCIA: {period_label}", "range": f"PERÍODO: {period_range}"},
        "filters": filters.to_dict(),
        "scope": {"families": [code.upper() for code in STOP_FAMILY_CODES], "equipment_total": len(vehicles)},
        "targets": target_rows,
        "active_stops": active_rows[:12],
        "active_summary": {"total": len(active_rows), "hours": round(sum(row["hours"] for row in active_rows), 2), "oldest_started_at": min((row["started_at"] for row in active_rows), default=None)},
        "monthly_summary": monthly_summary,
        "offenders": offenders,
        "reasons": reasons,
        "daily_trend": daily_trend,
        "projections": projections,
        "components": [],
        "data_availability": {
            "projections": bool(rows) and elapsed_days > 0,
            "components": False,
            "message": "Componentes ainda não estão disponíveis no cadastro atual." if not rows else "Projeção calculada com base nas horas do período.",
        },
        "performance": {"cached": False, "cache_ttl_seconds": STOP_CACHE_TTL_SECONDS, "query_duration_ms": round((monotonic() - started) * 1000, 2)},
    }
    _payload_cache[cache_key] = (now, payload)
    return payload
