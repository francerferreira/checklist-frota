from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models import MaintenanceSchedule, MaintenanceScheduleItem, MaintenanceWorkOrder, PreventivePlan, User, Vehicle
from app.services.maintenance_service import sync_work_order_for_item
from app.utils.timezone import now_manaus_naive, today_manaus


TRIGGERS = {"CALENDARIO", "HORIMETRO", "AMBOS"}
PRIORITIES = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}
OPEN_ORDER_STATUSES = {"ABERTA", "PROGRAMADA", "AGUARDANDO_MATERIAL", "EM_EXECUCAO", "REPROGRAMADA"}
PLAN_SOURCE_PREFIX = "PREVENTIVA_PCM:"


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value, field: str, default: int | None = None) -> int:
    if value in (None, "") and default is not None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalido.") from exc
    if number <= 0:
        raise ValueError(f"{field} deve ser maior que zero.")
    return number


def _non_negative_int(value, field: str, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalido.") from exc
    if number < 0:
        raise ValueError(f"{field} nao pode ser negativo.")
    return number


def _decimal(value, field: str, *, required: bool = False, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"Informe {field}.")
        return default
    try:
        parsed = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalido.") from exc
    if parsed < 0 or (required and parsed == 0):
        raise ValueError(f"{field} deve ser maior que zero.")
    return parsed


def _parse_date(value, field: str, default: date | None = None) -> date | None:
    if value in (None, ""):
        return default
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalida.") from exc


def plan_due_state(plan: PreventivePlan, *, reference_date: date | None = None) -> dict:
    reference_date = reference_date or today_manaus()
    state = plan.vehicle.operational_state if plan.vehicle else None
    current_hourmeter = Decimal(str(state.latest_hourmeter)) if state and state.latest_hourmeter is not None else None
    date_due = plan.next_due_date is not None and reference_date >= plan.next_due_date
    hourmeter_due = plan.next_due_hourmeter is not None and current_hourmeter is not None and current_hourmeter >= plan.next_due_hourmeter
    date_overdue = plan.next_due_date is not None and reference_date > plan.next_due_date + timedelta(days=plan.tolerance_days or 0)
    hourmeter_overdue = (
        plan.next_due_hourmeter is not None and current_hourmeter is not None
        and current_hourmeter > plan.next_due_hourmeter + Decimal(str(plan.tolerance_hourmeter or 0))
    )
    due = (plan.trigger_type in {"CALENDARIO", "AMBOS"} and date_due) or (plan.trigger_type in {"HORIMETRO", "AMBOS"} and hourmeter_due)
    overdue = (plan.trigger_type in {"CALENDARIO", "AMBOS"} and date_overdue) or (plan.trigger_type in {"HORIMETRO", "AMBOS"} and hourmeter_overdue)
    return {
        "status": "VENCIDA" if overdue else ("VENCENDO" if due else "EM_DIA"),
        "due": bool(due),
        "overdue": bool(overdue),
        "current_hourmeter": float(current_hourmeter) if current_hourmeter is not None else None,
    }


def _plan_payload(payload: dict, *, existing: PreventivePlan | None = None) -> dict:
    trigger = str(payload.get("trigger_type") or (existing.trigger_type if existing else "")).strip().upper()
    if trigger not in TRIGGERS:
        raise ValueError("Gatilho preventivo invalido.")
    vehicle_id = _positive_int(payload.get("vehicle_id") if "vehicle_id" in payload else (existing.vehicle_id if existing else None), "Equipamento")
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise ValueError("Equipamento ativo nao encontrado.")
    title = _clean(payload.get("title") if "title" in payload else (existing.title if existing else None))
    if not title:
        raise ValueError("Informe o titulo do plano preventivo.")
    interval_days_value = payload.get("interval_days") if "interval_days" in payload else (existing.interval_days if existing else None)
    interval_hourmeter_value = payload.get("interval_hourmeter") if "interval_hourmeter" in payload else (existing.interval_hourmeter if existing else None)
    interval_days = _positive_int(interval_days_value, "Periodicidade em dias") if trigger in {"CALENDARIO", "AMBOS"} else None
    interval_hourmeter = _decimal(interval_hourmeter_value, "Periodicidade em horimetro", required=True) if trigger in {"HORIMETRO", "AMBOS"} else None
    due_date_value = payload.get("next_due_date") if "next_due_date" in payload else (existing.next_due_date if existing else None)
    next_due_date = _parse_date(due_date_value, "Proxima data", today_manaus() + timedelta(days=interval_days or 0)) if trigger in {"CALENDARIO", "AMBOS"} else None
    if trigger in {"HORIMETRO", "AMBOS"}:
        state = vehicle.operational_state
        latest = Decimal(str(state.latest_hourmeter)) if state and state.latest_hourmeter is not None else None
        due_hourmeter_value = payload.get("next_due_hourmeter") if "next_due_hourmeter" in payload else (existing.next_due_hourmeter if existing else None)
        next_due_hourmeter = _decimal(due_hourmeter_value, "Proximo horimetro") or (latest + interval_hourmeter if latest is not None else None)
        if next_due_hourmeter is None:
            raise ValueError("Registre o horimetro atual ou informe o proximo horimetro do plano.")
    else:
        next_due_hourmeter = None
    priority = str(payload.get("priority") or (existing.priority if existing else "MEDIA")).strip().upper()
    if priority not in PRIORITIES:
        raise ValueError("Prioridade invalida.")
    mechanic_id = payload.get("assigned_mechanic_user_id") if "assigned_mechanic_user_id" in payload else (existing.assigned_mechanic_user_id if existing else None)
    if mechanic_id not in (None, ""):
        mechanic_id = _positive_int(mechanic_id, "Mecanico")
        mechanic = db.session.get(User, mechanic_id)
        if not mechanic or not mechanic.ativo or mechanic.tipo != "mecanico":
            raise ValueError("Mecanico ativo nao encontrado.")
    else:
        mechanic_id = None
    return {
        "vehicle_id": vehicle_id,
        "title": title,
        "description": _clean(payload.get("description") if "description" in payload else (existing.description if existing else None)),
        "trigger_type": trigger,
        "interval_days": interval_days,
        "interval_hourmeter": interval_hourmeter,
        "tolerance_days": _non_negative_int(payload.get("tolerance_days"), "Tolerancia em dias", existing.tolerance_days if existing else 0),
        "tolerance_hourmeter": _decimal(payload.get("tolerance_hourmeter"), "Tolerancia em horimetro", default=existing.tolerance_hourmeter if existing else Decimal("0")) or Decimal("0"),
        "next_due_date": next_due_date,
        "next_due_hourmeter": next_due_hourmeter,
        "priority": priority,
        "assigned_mechanic_user_id": mechanic_id,
        "estimated_duration_minutes": _positive_int(payload.get("estimated_duration_minutes"), "Duracao estimada", existing.estimated_duration_minutes if existing else 60),
    }


def create_preventive_plan(payload: dict, user_id: int) -> PreventivePlan:
    data = _plan_payload(payload)
    plan = PreventivePlan(code="PP-PEND", created_by_user_id=user_id, **data)
    db.session.add(plan)
    db.session.flush()
    plan.code = f"PP-{plan.id:06d}"
    db.session.commit()
    return plan


def update_preventive_plan(plan_id: int, payload: dict) -> PreventivePlan:
    plan = get_preventive_plan(plan_id)
    if plan.status == "ENCERRADO":
        raise ValueError("Plano encerrado nao pode ser alterado.")
    for field, value in _plan_payload(payload, existing=plan).items():
        setattr(plan, field, value)
    if "status" in payload:
        status = str(payload["status"] or "").strip().upper()
        if status not in {"ATIVO", "PAUSADO", "ENCERRADO"}:
            raise ValueError("Status do plano invalido.")
        plan.status = status
    db.session.commit()
    return plan


def get_preventive_plan(plan_id: int) -> PreventivePlan:
    plan = db.session.get(PreventivePlan, plan_id)
    if not plan:
        raise LookupError("Plano preventivo nao encontrado.")
    return plan


def list_preventive_plans() -> list[dict]:
    rows = PreventivePlan.query.order_by(PreventivePlan.status.asc(), PreventivePlan.next_due_date.asc().nullslast(), PreventivePlan.id.desc()).all()
    return [row.to_dict(plan_due_state(row)) for row in rows]


def _create_schedule_for_plan(plan: PreventivePlan, user_id: int) -> MaintenanceSchedule:
    sequence = plan.generation_sequence + 1
    schedule = MaintenanceSchedule(
        source_type="PREVENTIVA",
        source_key=f"{PLAN_SOURCE_PREFIX}{plan.id}:{sequence}",
        title=f"{plan.code} - {plan.title}",
        item_name=plan.title,
        status="PROGRAMADA",
        start_date=today_manaus(),
        end_date=today_manaus(),
        daily_capacity=1,
        created_by_user_id=user_id,
        assigned_mechanic_user_id=plan.assigned_mechanic_user_id,
        observation=f"Plano PCM {plan.code} | Prioridade {plan.priority} | {plan.description or 'Preventiva programada'}",
    )
    db.session.add(schedule)
    db.session.flush()
    item = MaintenanceScheduleItem(
        schedule_id=schedule.id,
        vehicle_id=plan.vehicle_id,
        assigned_mechanic_user_id=plan.assigned_mechanic_user_id,
        scheduled_date=today_manaus(),
        status="PROGRAMADO",
        observation=f"Gerado pelo plano {plan.code}",
    )
    db.session.add(item)
    db.session.flush()
    sync_work_order_for_item(item)
    plan.generation_sequence = sequence
    plan.last_generated_at = now_manaus_naive()
    return schedule


def generate_due_preventives(user_id: int, plan_id: int | None = None) -> list[dict]:
    query = PreventivePlan.query.filter_by(status="ATIVO")
    if plan_id:
        query = query.filter_by(id=plan_id)
    plans = query.order_by(PreventivePlan.id.asc()).all()
    if plan_id and not plans:
        raise LookupError("Plano preventivo ativo nao encontrado.")
    generated = []
    for plan in plans:
        due = plan_due_state(plan)
        if not due["due"]:
            continue
        active_schedule = MaintenanceSchedule.query.filter(
            MaintenanceSchedule.source_key.like(f"{PLAN_SOURCE_PREFIX}{plan.id}:%"),
            MaintenanceSchedule.status.in_({"ABERTA", "AGUARDANDO_MATERIAL", "PROGRAMADA", "EM_EXECUCAO"}),
        ).first()
        if active_schedule:
            continue
        schedule = _create_schedule_for_plan(plan, user_id)
        generated.append({"plan": plan.to_dict(plan_due_state(plan)), "schedule": schedule.to_dict(include_items=True, include_work_orders=True)})
    db.session.commit()
    return generated


def _plan_id_from_schedule(schedule: MaintenanceSchedule | None) -> int | None:
    source_key = str(schedule.source_key or "") if schedule else ""
    if not source_key.startswith(PLAN_SOURCE_PREFIX):
        return None
    try:
        return int(source_key.removeprefix(PLAN_SOURCE_PREFIX).split(":", 1)[0])
    except (TypeError, ValueError):
        return None


def advance_preventive_plan_after_completion(item: MaintenanceScheduleItem) -> None:
    plan_id = _plan_id_from_schedule(item.schedule)
    if not plan_id or not item.schedule or any(row.status != "INSTALADO" for row in item.schedule.items):
        return
    plan = db.session.get(PreventivePlan, plan_id)
    if not plan or plan.status != "ATIVO":
        return
    if plan.next_due_date and plan.interval_days:
        plan.next_due_date = plan.next_due_date + timedelta(days=plan.interval_days)
    if plan.next_due_hourmeter is not None and plan.interval_hourmeter is not None:
        plan.next_due_hourmeter = Decimal(str(plan.next_due_hourmeter)) + Decimal(str(plan.interval_hourmeter))


def build_pcm_agenda(year: int | None = None, month: int | None = None) -> dict:
    from app.services.maintenance_service import build_maintenance_overview

    overview = build_maintenance_overview(year=year, month=month)
    plans = list_preventive_plans()
    due_plans = [plan for plan in plans if (plan.get("due") or {}).get("due")]
    return {"agenda": overview, "preventive_plans": plans, "summary": {"planos": len(plans), "vencendo_ou_vencidos": len(due_plans)}}


def build_backlog() -> list[dict]:
    today = today_manaus()
    rows = MaintenanceWorkOrder.query.filter(MaintenanceWorkOrder.status.in_(OPEN_ORDER_STATUSES)).order_by(MaintenanceWorkOrder.scheduled_date.asc().nullslast()).all()
    result = []
    for order in rows:
        schedule = order.schedule
        plan_id = _plan_id_from_schedule(schedule)
        plan = db.session.get(PreventivePlan, plan_id) if plan_id else None
        scheduled = order.scheduled_date
        age_days = max(0, (today - scheduled).days) if scheduled else 0
        result.append({
            "work_order": order.to_dict(),
            "source": schedule.source_origin_type() if schedule else "-",
            "priority": plan.priority if plan else ("ALTA" if age_days > 0 else "MEDIA"),
            "age_days": age_days,
            "overdue": bool(scheduled and scheduled < today),
            "blockers": schedule.blocker_summary() if schedule else {},
            "estimated_duration_minutes": plan.estimated_duration_minutes if plan else None,
        })
    return result


def build_pcm_programming_window(*, start_date: date, end_date: date, daily_capacity_minutes: int = 480) -> dict:
    """Projecao somente leitura de carga e janelas preventivas no horizonte informado."""
    if end_date < start_date:
        raise ValueError("A data final nao pode ser anterior a data inicial.")
    if (end_date - start_date).days > 90:
        raise ValueError("O horizonte do PCM pode ter no maximo 90 dias.")
    if daily_capacity_minutes < 60 or daily_capacity_minutes > 1_440:
        raise ValueError("A capacidade diaria deve ficar entre 60 e 1440 minutos.")

    plans = PreventivePlan.query.filter_by(status="ATIVO").all()
    plans_by_id = {plan.id: plan for plan in plans}
    active_schedule_plan_ids = {
        plan_id
        for schedule in MaintenanceSchedule.query.filter(MaintenanceSchedule.status.in_({"ABERTA", "AGUARDANDO_MATERIAL", "PROGRAMADA", "EM_EXECUCAO"})).all()
        if (plan_id := _plan_id_from_schedule(schedule))
    }
    days = {}
    cursor = start_date
    while cursor <= end_date:
        days[cursor] = {"date": cursor, "occupied_minutes": 0, "scheduled_items": 0, "completed_items": 0, "not_executed_items": 0}
        cursor += timedelta(days=1)

    items = MaintenanceScheduleItem.query.filter(
        MaintenanceScheduleItem.scheduled_date >= start_date,
        MaintenanceScheduleItem.scheduled_date <= end_date,
    ).all()
    for item in items:
        if not item.scheduled_date or item.status == "CANCELADO":
            continue
        plan = plans_by_id.get(_plan_id_from_schedule(item.schedule))
        duration = int(plan.estimated_duration_minutes) if plan else 60
        row = days[item.scheduled_date]
        row["occupied_minutes"] += duration
        row["scheduled_items"] += 1
        row["completed_items"] += int(item.status == "INSTALADO")
        row["not_executed_items"] += int(item.status == "NAO_EXECUTADO")

    today = today_manaus()
    compliance_base = compliance_done = 0
    daily_rows = []
    for current, row in days.items():
        completed = row["completed_items"]
        planned = row["scheduled_items"]
        if current <= today:
            compliance_base += planned
            compliance_done += completed
        daily_rows.append({
            "date": current.isoformat(),
            "capacity_minutes": daily_capacity_minutes,
            "occupied_minutes": row["occupied_minutes"],
            "free_minutes": max(daily_capacity_minutes - row["occupied_minutes"], 0),
            "overloaded_minutes": max(row["occupied_minutes"] - daily_capacity_minutes, 0),
            "scheduled_items": planned,
            "completed_items": completed,
            "not_executed_items": row["not_executed_items"],
        })

    allocated_minutes = {current: row["occupied_minutes"] for current, row in days.items()}
    recommendations = []
    for plan in plans:
        due = plan_due_state(plan, reference_date=today)
        if not due["due"] or plan.id in active_schedule_plan_ids:
            continue
        if plan.next_due_date:
            window_start = plan.next_due_date - timedelta(days=plan.tolerance_days or 0)
            window_end = plan.next_due_date + timedelta(days=plan.tolerance_days or 0)
        else:
            window_start, window_end = start_date, end_date
        candidate_start = max(start_date, window_start)
        candidate_end = min(end_date, window_end)
        recommended_date = None
        if candidate_start <= candidate_end:
            cursor = candidate_start
            while cursor <= candidate_end:
                if allocated_minutes[cursor] + int(plan.estimated_duration_minutes) <= daily_capacity_minutes:
                    recommended_date = cursor
                    allocated_minutes[cursor] += int(plan.estimated_duration_minutes)
                    break
                cursor += timedelta(days=1)
        recommendations.append({
            "plan_id": plan.id,
            "code": plan.code,
            "title": plan.title,
            "vehicle": plan.vehicle.to_dict() if plan.vehicle else None,
            "priority": plan.priority,
            "estimated_duration_minutes": plan.estimated_duration_minutes,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "recommended_date": recommended_date.isoformat() if recommended_date else None,
            "status": "PROGRAMAR" if recommended_date else "SEM_CAPACIDADE",
            "due_status": due["status"],
        })
    recommendations.sort(key=lambda row: (row["status"] != "SEM_CAPACIDADE", row["window_end"], row["priority"], row["code"]))
    total_capacity = len(daily_rows) * daily_capacity_minutes
    occupied = sum(row["occupied_minutes"] for row in daily_rows)
    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat(), "daily_capacity_minutes": daily_capacity_minutes},
        "summary": {
            "total_capacity_minutes": total_capacity,
            "occupied_minutes": occupied,
            "free_minutes": max(total_capacity - occupied, 0),
            "overloaded_days": sum(1 for row in daily_rows if row["overloaded_minutes"] > 0),
            "preventive_compliance_percent": round((compliance_done / compliance_base) * 100, 1) if compliance_base else 0.0,
            "compliance_base": compliance_base,
            "pending_preventive_windows": len(recommendations),
        },
        "days": daily_rows,
        "recommended_windows": recommendations,
    }
