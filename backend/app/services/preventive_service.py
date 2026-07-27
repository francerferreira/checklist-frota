"""Regras centrais de cálculo e lançamento das preventivas.

Este módulo concentra as regras de horímetro para que as telas do Desktop e
do Web Mobile usem a mesma fonte de verdade.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import EquipmentOperationalState, HourmeterReading, PreventiveExecution, PreventivePlan, Vehicle
from app.utils.timezone import MANAUS_TZ, now_manaus_naive, today_manaus


DEFAULT_STALE_READING_DAYS = 2
MAX_HOURMETER_DELTA = Decimal("400")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100.00")


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _parse_recorded_at(value) -> datetime:
    if value in (None, ""):
        return now_manaus_naive()
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Data da leitura invalida.") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(MANAUS_TZ).replace(tzinfo=None)
    if parsed > now_manaus_naive():
        raise ValueError("Data da leitura nao pode estar no futuro.")
    return parsed


def _ensure_operational_state(vehicle_id: int) -> EquipmentOperationalState:
    state = EquipmentOperationalState.query.filter_by(vehicle_id=vehicle_id).first()
    if state:
        return state
    state = EquipmentOperationalState(vehicle_id=vehicle_id)
    db.session.add(state)
    return state


def calculate_cycle_progress(
    current_hourmeter,
    last_preventive_hourmeter,
    next_preventive_hourmeter,
) -> dict:
    """Calcula o avanço do ciclo sem acessar o banco.

    O resultado é deliberadamente simples para ser usado por APIs, Desktop e
    Mobile sem cada tela repetir a mesma matemática.
    """
    current = _as_decimal(current_hourmeter)
    last = _as_decimal(last_preventive_hourmeter)
    next_due = _as_decimal(next_preventive_hourmeter)
    if current is None or last is None or next_due is None:
        return {
            "hours_used": None,
            "hours_remaining": None,
            "cycle_hours": None,
            "percent_used": None,
            "status": "SEM_DADOS",
        }
    cycle = next_due - last
    if cycle <= _ZERO:
        return {
            "hours_used": None,
            "hours_remaining": None,
            "cycle_hours": None,
            "percent_used": None,
            "status": "SEM_DADOS",
        }
    used = max(current - last, _ZERO)
    remaining = next_due - current
    percent = (used / cycle * _HUNDRED).quantize(Decimal("0.01"))
    if remaining <= _ZERO:
        status = "VENCIDA"
    elif remaining <= Decimal("20"):
        status = "CRITICA"
    elif remaining <= Decimal("100"):
        status = "PROXIMA"
    elif remaining <= Decimal("200"):
        status = "ATENCAO"
    else:
        status = "NO_PRAZO"
    return {
        "hours_used": _number(used),
        "hours_remaining": _number(remaining),
        "cycle_hours": _number(cycle),
        "percent_used": float(percent),
        "status": status,
    }


def _latest_completed_execution(plan: PreventivePlan):
    try:
        return (
            PreventiveExecution.query.filter(
                PreventiveExecution.preventive_plan_id == plan.id,
                PreventiveExecution.status == "CONCLUIDA",
            )
            .order_by(PreventiveExecution.completed_at.desc().nullslast(), PreventiveExecution.id.desc())
            .first()
        )
    except OperationalError:
        # Permite que o módulo continue legível durante uma atualização gradual
        # de banco, antes da migration da etapa 3 ser aplicada.
        db.session.rollback()
        return None


def calculate_plan_state(
    plan: PreventivePlan,
    *,
    reference_date: date | None = None,
    stale_days: int = DEFAULT_STALE_READING_DAYS,
) -> dict:
    """Retorna o estado completo de um plano preventivo."""
    reference_date = reference_date or today_manaus()
    state = plan.vehicle.operational_state if plan.vehicle else None
    current = _as_decimal(state.latest_hourmeter if state else None)
    latest_at = state.latest_hourmeter_at if state else None
    date_due = bool(plan.next_due_date and reference_date >= plan.next_due_date)
    hourmeter_due = bool(plan.next_due_hourmeter is not None and current is not None and current >= plan.next_due_hourmeter)
    date_overdue = bool(
        plan.next_due_date
        and reference_date > plan.next_due_date + timedelta(days=plan.tolerance_days or 0)
    )
    hourmeter_overdue = bool(
        plan.next_due_hourmeter is not None
        and current is not None
        and current > plan.next_due_hourmeter + Decimal(str(plan.tolerance_hourmeter or 0))
    )
    due = (plan.trigger_type in {"CALENDARIO", "AMBOS"} and date_due) or (
        plan.trigger_type in {"HORIMETRO", "AMBOS"} and hourmeter_due
    )
    overdue = (plan.trigger_type in {"CALENDARIO", "AMBOS"} and date_overdue) or (
        plan.trigger_type in {"HORIMETRO", "AMBOS"} and hourmeter_overdue
    )

    execution = _latest_completed_execution(plan)
    last_preventive_hm = _as_decimal(execution.hourmeter_execution if execution else None)
    last_preventive_date = execution.completed_at.date() if execution and execution.completed_at else None
    if last_preventive_hm is None and plan.next_due_hourmeter is not None and plan.interval_hourmeter is not None:
        last_preventive_hm = _as_decimal(plan.next_due_hourmeter) - _as_decimal(plan.interval_hourmeter)
    cycle = calculate_cycle_progress(current, last_preventive_hm, plan.next_due_hourmeter)
    stale = bool(
        latest_at
        and (reference_date - latest_at.date()).days > stale_days
    )
    calculation_status = "LEITURA_DESATUALIZADA" if stale else cycle["status"]
    return {
        "status": "VENCIDA" if overdue else ("VENCENDO" if due else "EM_DIA"),
        "calculation_status": calculation_status,
        "due": bool(due),
        "overdue": bool(overdue),
        "date_due": date_due,
        "hourmeter_due": hourmeter_due,
        "date_overdue": date_overdue,
        "hourmeter_overdue": hourmeter_overdue,
        "current_hourmeter": _number(current),
        "last_reading_at": latest_at.isoformat() if latest_at else None,
        "last_preventive_hourmeter": _number(last_preventive_hm),
        "last_preventive_date": last_preventive_date.isoformat() if last_preventive_date else None,
        "next_due_hourmeter": _number(_as_decimal(plan.next_due_hourmeter)),
        "next_due_date": plan.next_due_date.isoformat() if plan.next_due_date else None,
        "stale_reading": stale,
        "hours_used": cycle["hours_used"],
        "hours_remaining": cycle["hours_remaining"],
        "cycle_hours": cycle["cycle_hours"],
        "percent_used": cycle["percent_used"],
    }


def calculate_next_due(plan: PreventivePlan) -> dict:
    """Calcula o próximo vencimento após a conclusão de um ciclo."""
    next_date = (
        plan.next_due_date + timedelta(days=plan.interval_days)
        if plan.next_due_date and plan.interval_days
        else plan.next_due_date
    )
    next_hourmeter = (
        _as_decimal(plan.next_due_hourmeter) + _as_decimal(plan.interval_hourmeter)
        if plan.next_due_hourmeter is not None and plan.interval_hourmeter is not None
        else _as_decimal(plan.next_due_hourmeter)
    )
    return {"next_due_date": next_date, "next_due_hourmeter": next_hourmeter}


def register_hourmeter(vehicle_id: int, payload: dict, user_id: int) -> HourmeterReading:
    """Registra uma leitura com validações cronológicas e rastreabilidade."""
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise LookupError("Equipamento ativo nao encontrado.")
    try:
        reading = Decimal(str(payload.get("reading"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Informe um horimetro numerico valido.") from exc
    if reading < 0:
        raise ValueError("O horimetro nao pode ser negativo.")
    recorded_at = _parse_recorded_at(payload.get("recorded_at"))
    duplicate = HourmeterReading.query.filter_by(vehicle_id=vehicle_id, recorded_at=recorded_at).first()
    if duplicate:
        raise ValueError("Ja existe uma leitura para este equipamento nesta data e hora.")
    previous = (
        HourmeterReading.query.filter(
            HourmeterReading.vehicle_id == vehicle_id,
            HourmeterReading.recorded_at < recorded_at,
        )
        .order_by(HourmeterReading.recorded_at.desc())
        .first()
    )
    following = (
        HourmeterReading.query.filter(
            HourmeterReading.vehicle_id == vehicle_id,
            HourmeterReading.recorded_at > recorded_at,
        )
        .order_by(HourmeterReading.recorded_at.asc())
        .first()
    )
    if previous and reading < previous.reading:
        raise ValueError("A leitura nao pode ser menor que o horimetro anterior.")
    if following and reading > following.reading:
        raise ValueError("A leitura nao pode ser maior que o horimetro posterior.")
    difference = reading - previous.reading if previous else None
    validation_status = "ALERTA_VARIACAO" if difference is not None and difference > MAX_HOURMETER_DELTA else "VALIDA"
    item = HourmeterReading(
        vehicle_id=vehicle_id,
        reading=reading,
        recorded_at=recorded_at,
        source="MANUAL",
        evidence_path=_clean(payload.get("evidence_path")),
        notes=_clean(payload.get("notes")),
        created_by_user_id=user_id,
        previous_reading=previous.reading if previous else None,
        difference_hours=difference,
        validation_status=validation_status,
    )
    db.session.add(item)
    state = _ensure_operational_state(vehicle_id)
    if state.latest_hourmeter_at is None or recorded_at >= state.latest_hourmeter_at:
        state.latest_hourmeter = reading
        state.latest_hourmeter_at = recorded_at
    db.session.commit()
    return item
