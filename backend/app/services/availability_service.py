from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models import EquipmentOperationalState, EquipmentStatusEvent, HourmeterReading, Vehicle
from app.utils.timezone import MANAUS_TZ, now_manaus_naive, today_manaus


TRACKED_STATUSES = {"DISPONIVEL", "INDISPONIVEL", "RESTRICAO", "MANUTENCAO"}
AVAILABLE_STATUSES = {"DISPONIVEL", "RESTRICAO"}
STATUS_REQUIRING_REASON = {"INDISPONIVEL", "RESTRICAO", "MANUTENCAO"}


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_datetime(value, *, field_name: str) -> datetime:
    if value in (None, ""):
        return now_manaus_naive()
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalida.") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(MANAUS_TZ).replace(tzinfo=None)
    if parsed > now_manaus_naive():
        raise ValueError(f"{field_name} nao pode estar no futuro.")
    return parsed


def _parse_date(value, *, default: date, field_name: str) -> date:
    if value in (None, ""):
        return default
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalida.") from exc


def ensure_operational_state(vehicle_id: int) -> EquipmentOperationalState:
    state = EquipmentOperationalState.query.filter_by(vehicle_id=vehicle_id).first()
    if state:
        return state
    state = EquipmentOperationalState(vehicle_id=vehicle_id)
    db.session.add(state)
    return state


def seed_operational_states() -> int:
    existing_ids = {row[0] for row in db.session.query(EquipmentOperationalState.vehicle_id).all()}
    missing_ids = [row[0] for row in db.session.query(Vehicle.id).filter(~Vehicle.id.in_(existing_ids)).all()]
    for vehicle_id in missing_ids:
        db.session.add(EquipmentOperationalState(vehicle_id=vehicle_id))
    if missing_ids:
        db.session.commit()
    return len(missing_ids)


def set_operational_status(vehicle_id: int, payload: dict, user_id: int) -> dict:
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise LookupError("Equipamento ativo nao encontrado.")
    status = str(payload.get("status") or "").strip().upper()
    if status not in TRACKED_STATUSES:
        raise ValueError("Status operacional invalido.")
    reason = _clean(payload.get("reason"))
    if status in STATUS_REQUIRING_REASON and not reason:
        raise ValueError("Informe o motivo para este status operacional.")
    started_at = parse_datetime(payload.get("started_at"), field_name="Data do status")
    open_event = (
        EquipmentStatusEvent.query.filter_by(vehicle_id=vehicle_id, ended_at=None)
        .order_by(EquipmentStatusEvent.started_at.desc()).first()
    )
    if open_event and started_at < open_event.started_at:
        raise ValueError("A nova situacao nao pode iniciar antes do status atual.")
    observation = _clean(payload.get("observation"))
    evidence_path = _clean(payload.get("evidence_path"))
    if open_event and open_event.status == status:
        open_event.reason = reason
        open_event.observation = observation
        open_event.evidence_path = evidence_path
        event = open_event
    else:
        if open_event:
            open_event.ended_at = started_at
        event = EquipmentStatusEvent(
            vehicle_id=vehicle_id, status=status, reason=reason,
            observation=observation, evidence_path=evidence_path, source="MANUAL",
            started_at=started_at, created_by_user_id=user_id,
        )
        db.session.add(event)
    state = ensure_operational_state(vehicle_id)
    state.operational_status = status
    state.status_updated_at = started_at
    state.status_reason = reason
    state.status_evidence_path = evidence_path
    db.session.commit()
    return {"state": state.to_dict(), "event": event.to_dict()}


def record_hourmeter(vehicle_id: int, payload: dict, user_id: int) -> HourmeterReading:
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise LookupError("Equipamento ativo nao encontrado.")
    try:
        reading = Decimal(str(payload.get("reading"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Informe um horimetro numerico valido.") from exc
    if reading < 0:
        raise ValueError("O horimetro nao pode ser negativo.")
    recorded_at = parse_datetime(payload.get("recorded_at"), field_name="Data da leitura")
    previous = (HourmeterReading.query.filter(
        HourmeterReading.vehicle_id == vehicle_id, HourmeterReading.recorded_at < recorded_at,
    ).order_by(HourmeterReading.recorded_at.desc()).first())
    following = (HourmeterReading.query.filter(
        HourmeterReading.vehicle_id == vehicle_id, HourmeterReading.recorded_at > recorded_at,
    ).order_by(HourmeterReading.recorded_at.asc()).first())
    if previous and reading < previous.reading:
        raise ValueError("A leitura nao pode ser menor que o horimetro anterior.")
    if following and reading > following.reading:
        raise ValueError("A leitura nao pode ser maior que o horimetro posterior.")
    item = HourmeterReading(
        vehicle_id=vehicle_id, reading=reading, recorded_at=recorded_at, source="MANUAL",
        evidence_path=_clean(payload.get("evidence_path")), notes=_clean(payload.get("notes")),
        created_by_user_id=user_id,
    )
    db.session.add(item)
    state = ensure_operational_state(vehicle_id)
    if state.latest_hourmeter_at is None or recorded_at >= state.latest_hourmeter_at:
        state.latest_hourmeter = reading
        state.latest_hourmeter_at = recorded_at
    db.session.commit()
    return item


def list_status_history(vehicle_id: int) -> list[dict]:
    if not db.session.get(Vehicle, vehicle_id):
        raise LookupError("Equipamento nao encontrado.")
    rows = EquipmentStatusEvent.query.filter_by(vehicle_id=vehicle_id).order_by(
        EquipmentStatusEvent.started_at.desc()).all()
    return [row.to_dict() for row in rows]


def list_hourmeter_readings(vehicle_id: int) -> list[dict]:
    if not db.session.get(Vehicle, vehicle_id):
        raise LookupError("Equipamento nao encontrado.")
    rows = HourmeterReading.query.filter_by(vehicle_id=vehicle_id).order_by(
        HourmeterReading.recorded_at.desc()).all()
    return [row.to_dict() for row in rows]


def build_availability_overview(*, date_from=None, date_to=None,
                                family_id: int | None = None,
                                location_id: int | None = None) -> dict:
    today = today_manaus()
    start_date = _parse_date(date_from, default=today, field_name="Data inicial")
    end_date = _parse_date(date_to, default=today, field_name="Data final")
    if end_date < start_date:
        raise ValueError("A data final deve ser igual ou posterior a data inicial.")
    window_start = datetime.combine(start_date, time.min)
    window_end = min(datetime.combine(end_date, time.max), now_manaus_naive())
    query = Vehicle.query.filter_by(ativo=True).join(Vehicle.equipment_profile)
    if family_id:
        query = query.filter_by(family_id=family_id)
    if location_id:
        query = query.filter_by(operational_location_id=location_id)
    vehicles = query.order_by(Vehicle.frota.asc()).all()
    vehicle_ids = [vehicle.id for vehicle in vehicles]
    events_by_vehicle = {vehicle_id: [] for vehicle_id in vehicle_ids}
    if vehicle_ids and window_end >= window_start:
        events = EquipmentStatusEvent.query.filter(
            EquipmentStatusEvent.vehicle_id.in_(vehicle_ids),
            EquipmentStatusEvent.started_at <= window_end,
            db.or_(EquipmentStatusEvent.ended_at.is_(None), EquipmentStatusEvent.ended_at >= window_start),
        ).all()
        for event in events:
            events_by_vehicle[event.vehicle_id].append(event)
    rows, percentages = [], []
    counts = {status: 0 for status in ("SEM_APONTAMENTO", *sorted(TRACKED_STATUSES))}
    for vehicle in vehicles:
        state = vehicle.operational_state
        current_status = state.operational_status if state else "SEM_APONTAMENTO"
        counts[current_status] = counts.get(current_status, 0) + 1
        covered_seconds = available_seconds = 0.0
        for event in events_by_vehicle.get(vehicle.id, []):
            event_start = max(event.started_at, window_start)
            event_end = min(event.ended_at or window_end, window_end)
            seconds = max(0.0, (event_end - event_start).total_seconds())
            covered_seconds += seconds
            if event.status in AVAILABLE_STATUSES:
                available_seconds += seconds
        availability = round(available_seconds / covered_seconds * 100, 2) if covered_seconds else None
        if availability is not None:
            percentages.append(availability)
        profile = vehicle.equipment_profile
        rows.append({
            "vehicle": vehicle.to_dict(),
            "family": profile.family.to_dict() if profile and profile.family else None,
            "location": profile.location.to_dict() if profile and profile.location else None,
            "availability_percentage": availability,
            "covered_hours": round(covered_seconds / 3600, 2),
        })
    return {
        "period": {"date_from": start_date.isoformat(), "date_to": end_date.isoformat()},
        "summary": {
            "total": len(vehicles), "status_counts": counts,
            "average_availability_percentage": round(sum(percentages) / len(percentages), 2) if percentages else None,
            "measured_equipment": len(percentages),
        },
        "rows": rows,
    }
