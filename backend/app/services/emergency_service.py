from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import (
    EmergencyEvent,
    EquipmentOperationalState,
    EquipmentStatusEvent,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    User,
    Vehicle,
    WorkOrderExecution,
)
from app.services.availability_service import ensure_operational_state, parse_datetime
from app.services.maintenance_service import sync_work_order_for_item
from app.utils.timezone import now_manaus_naive, today_manaus


SEVERITIES = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} invalido.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} invalido.")
    return parsed


def _set_equipment_status(vehicle_id: int, status: str, reason: str, user_id: int, *, evidence_path: str | None = None) -> None:
    changed_at = now_manaus_naive()
    open_event = (
        EquipmentStatusEvent.query.filter_by(vehicle_id=vehicle_id, ended_at=None)
        .order_by(EquipmentStatusEvent.started_at.desc())
        .first()
    )
    if open_event and open_event.status != status:
        open_event.ended_at = max(changed_at, open_event.started_at)
    if not open_event or open_event.status != status:
        db.session.add(
            EquipmentStatusEvent(
                vehicle_id=vehicle_id,
                status=status,
                reason=reason,
                evidence_path=evidence_path,
                source="AUTOMACAO",
                started_at=changed_at,
                created_by_user_id=user_id,
            )
        )
    state = ensure_operational_state(vehicle_id)
    state.operational_status = status
    state.status_updated_at = changed_at
    state.status_reason = reason
    state.status_evidence_path = evidence_path


def create_emergency(payload: dict, user_id: int) -> EmergencyEvent:
    vehicle_id = _positive_int(payload.get("vehicle_id"), "Equipamento")
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise LookupError("Equipamento ativo nao encontrado.")
    severity = str(payload.get("severity") or "").strip().upper()
    if severity not in SEVERITIES:
        raise ValueError("Criticidade invalida.")
    title = _clean(payload.get("title"))
    description = _clean(payload.get("description"))
    if not title or not description:
        raise ValueError("Informe titulo e descricao da emergencia.")
    opened_at = parse_datetime(payload.get("opened_at"), field_name="Data da emergencia")
    emergency = EmergencyEvent(
        event_number="EMG-PEND",
        vehicle_id=vehicle_id,
        severity=severity,
        equipment_stopped=bool(payload.get("equipment_stopped", False)),
        title=title,
        description=description,
        location=_clean(payload.get("location")),
        evidence_path=_clean(payload.get("evidence_path")),
        reported_by_user_id=user_id,
        opened_at=opened_at,
    )
    db.session.add(emergency)
    db.session.flush()
    emergency.event_number = f"EMG-{emergency.id:06d}"
    if emergency.equipment_stopped:
        _set_equipment_status(
            vehicle_id,
            "MANUTENCAO",
            f"Emergencial {emergency.event_number}: {title}",
            user_id,
            evidence_path=emergency.evidence_path,
        )
    db.session.commit()
    return emergency


def list_emergencies(*, status: str | None = None, mechanic_id: int | None = None) -> list[dict]:
    query = EmergencyEvent.query
    if status:
        query = query.filter(EmergencyEvent.status == str(status).strip().upper())
    if mechanic_id:
        query = query.filter(EmergencyEvent.assigned_mechanic_user_id == mechanic_id)
    return [row.to_dict() for row in query.order_by(EmergencyEvent.opened_at.desc()).all()]


def get_emergency(emergency_id: int) -> EmergencyEvent:
    emergency = db.session.get(EmergencyEvent, emergency_id)
    if not emergency:
        raise LookupError("Emergencia nao encontrada.")
    return emergency


def triage_emergency(emergency_id: int, payload: dict, user_id: int) -> EmergencyEvent:
    emergency = get_emergency(emergency_id)
    if emergency.status not in {"ABERTA", "TRIAGEM"}:
        raise ValueError("Somente emergencia aberta pode ser triada.")
    mechanic_id = _positive_int(payload.get("assigned_mechanic_user_id"), "Mecanico")
    mechanic = db.session.get(User, mechanic_id)
    if not mechanic or not mechanic.ativo or mechanic.tipo != "mecanico":
        raise ValueError("Mecanico ativo nao encontrado.")
    emergency.assigned_mechanic_user_id = mechanic_id
    emergency.triaged_by_user_id = user_id
    emergency.acknowledged_at = emergency.acknowledged_at or now_manaus_naive()
    emergency.status = "TRIAGEM"
    db.session.commit()
    return emergency


def convert_emergency_to_work_order(emergency_id: int, payload: dict, user_id: int) -> EmergencyEvent:
    emergency = get_emergency(emergency_id)
    if emergency.work_order_id:
        raise ValueError("Esta emergencia ja possui ordem de servico.")
    mechanic_id = payload.get("assigned_mechanic_user_id") or emergency.assigned_mechanic_user_id
    mechanic_id = _positive_int(mechanic_id, "Mecanico")
    mechanic = db.session.get(User, mechanic_id)
    if not mechanic or not mechanic.ativo or mechanic.tipo != "mecanico":
        raise ValueError("Mecanico ativo nao encontrado.")
    raw_date = payload.get("scheduled_date")
    try:
        scheduled_date = date.fromisoformat(str(raw_date)) if raw_date else today_manaus()
    except ValueError as exc:
        raise ValueError("Data programada invalida.") from exc

    schedule = MaintenanceSchedule(
        source_type="ATIVIDADE",
        source_key=f"EMERGENCIA:{emergency.id}",
        title=f"Emergencial {emergency.event_number} - {emergency.title}",
        item_name=emergency.title,
        status="EM_EXECUCAO",
        start_date=scheduled_date,
        end_date=scheduled_date,
        daily_capacity=1,
        created_by_user_id=user_id,
        assigned_mechanic_user_id=mechanic_id,
        observation=emergency.description,
    )
    db.session.add(schedule)
    db.session.flush()
    item = MaintenanceScheduleItem(
        schedule_id=schedule.id,
        vehicle_id=emergency.vehicle_id,
        assigned_mechanic_user_id=mechanic_id,
        scheduled_date=scheduled_date,
        status="PROGRAMADO",
        observation=f"Origem: {emergency.event_number}",
    )
    db.session.add(item)
    db.session.flush()
    work_order = sync_work_order_for_item(item)
    db.session.flush()
    db.session.add(WorkOrderExecution(work_order_id=work_order.id, failure_started_at=emergency.opened_at))
    emergency.assigned_mechanic_user_id = mechanic_id
    emergency.triaged_by_user_id = emergency.triaged_by_user_id or user_id
    emergency.acknowledged_at = emergency.acknowledged_at or now_manaus_naive()
    emergency.converted_at = now_manaus_naive()
    emergency.status = "CONVERTIDA"
    emergency.work_order_id = work_order.id
    db.session.commit()
    return emergency


def get_work_order(work_order_id: int) -> MaintenanceWorkOrder:
    work_order = db.session.get(MaintenanceWorkOrder, work_order_id)
    if not work_order:
        raise LookupError("Ordem de servico nao encontrada.")
    return work_order


def _execution_for(work_order: MaintenanceWorkOrder) -> WorkOrderExecution:
    execution = work_order.execution
    if not execution:
        raise ValueError("Esta OS nao pertence ao fluxo emergencial.")
    return execution


def start_work_order(work_order_id: int, payload: dict) -> MaintenanceWorkOrder:
    work_order = get_work_order(work_order_id)
    execution = _execution_for(work_order)
    diagnosis = _clean(payload.get("diagnosis"))
    if not diagnosis:
        raise ValueError("Informe o diagnostico antes de iniciar o reparo.")
    execution.diagnosis = diagnosis
    execution.before_evidence_path = _clean(payload.get("before_evidence_path")) or execution.before_evidence_path
    execution.repair_started_at = execution.repair_started_at or now_manaus_naive()
    work_order.status = "EM_EXECUCAO"
    work_order.schedule.status = "EM_EXECUCAO"
    db.session.commit()
    return work_order


def complete_repair(work_order_id: int, payload: dict) -> MaintenanceWorkOrder:
    work_order = get_work_order(work_order_id)
    execution = _execution_for(work_order)
    if not execution.repair_started_at:
        raise ValueError("Inicie a OS antes de concluir o reparo.")
    service = _clean(payload.get("service_performed"))
    evidence = _clean(payload.get("after_evidence_path"))
    if not service or not evidence:
        raise ValueError("Informe o servico executado e a evidencia posterior.")
    execution.service_performed = service
    execution.after_evidence_path = evidence
    execution.repair_completed_at = now_manaus_naive()
    db.session.commit()
    return work_order


def record_operational_test(work_order_id: int, payload: dict) -> MaintenanceWorkOrder:
    work_order = get_work_order(work_order_id)
    execution = _execution_for(work_order)
    if not execution.repair_completed_at:
        raise ValueError("Conclua o reparo antes do teste operacional.")
    result = str(payload.get("test_result") or "").strip().upper()
    notes = _clean(payload.get("test_notes"))
    if result not in {"APROVADO", "REPROVADO"}:
        raise ValueError("Resultado do teste invalido.")
    if result == "REPROVADO" and not notes:
        raise ValueError("Informe o motivo da reprovacao do teste.")
    execution.test_result = result
    execution.test_notes = notes
    execution.test_evidence_path = _clean(payload.get("test_evidence_path"))
    execution.release_status = "PENDENTE" if result == "APROVADO" else "NAO_LIBERADO"
    db.session.commit()
    return work_order


def release_work_order(work_order_id: int, user_id: int) -> MaintenanceWorkOrder:
    work_order = get_work_order(work_order_id)
    execution = _execution_for(work_order)
    if execution.test_result != "APROVADO":
        raise ValueError("A liberacao exige teste operacional aprovado.")
    released_at = now_manaus_naive()
    execution.release_status = "LIBERADO"
    execution.released_at = released_at
    execution.released_by_user_id = user_id
    work_order.status = "CONCLUIDA"
    item = work_order.schedule_item
    item.status = "INSTALADO"
    item.photo_after = execution.after_evidence_path
    item.executed_by_user_id = user_id
    item.executed_at = released_at
    work_order.schedule.status = "CONCLUIDA"
    emergency = EmergencyEvent.query.filter_by(work_order_id=work_order.id).first()
    if emergency:
        emergency.status = "ENCERRADA"
        emergency.closed_at = released_at
    _set_equipment_status(
        work_order.vehicle_id,
        "DISPONIVEL",
        f"Liberado apos teste aprovado da {work_order.order_number}",
        user_id,
        evidence_path=execution.test_evidence_path or execution.after_evidence_path,
    )
    db.session.commit()
    return work_order
