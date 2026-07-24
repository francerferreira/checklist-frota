from __future__ import annotations

import hashlib
import json
import re

from app.extensions import db
from app.models import MaintenanceScheduleItem, MobileSyncOperation, Vehicle
from app.services.availability_service import parse_datetime, record_hourmeter
from app.services.auth_service import user_has_mechanic_workspace_access
from app.services.emergency_service import (
    complete_repair,
    create_emergency,
    get_work_order,
    record_operational_test,
    release_work_order,
    start_work_order,
)
from app.services.maintenance_service import update_schedule_item
from app.utils.timezone import now_manaus_naive


MOBILE_OPERATION_TYPES = {
    "HORIMETRO", "EMERGENCIA", "OS_INICIAR", "OS_CONCLUIR", "OS_TESTAR", "OS_LIBERAR",
    "MANUTENCAO_ATUALIZAR_ITEM",
}
ACCESS_CODE_PATTERN = re.compile(r"^CF-ATIVO-(\d+)$", re.IGNORECASE)


class MobileOperationConflict(ValueError):
    pass


class MobileOperationAccessError(PermissionError):
    pass


def mobile_access_code(vehicle_id: int) -> str:
    return f"CF-ATIVO-{int(vehicle_id):06d}"


def resolve_mobile_asset(access_code: str) -> Vehicle:
    code = str(access_code or "").strip().upper()
    match = ACCESS_CODE_PATTERN.fullmatch(code)
    if not match:
        raise LookupError("Codigo do ativo invalido.")
    vehicle = db.session.get(Vehicle, int(match.group(1)))
    if not vehicle or not vehicle.ativo:
        raise LookupError("Equipamento ativo nao encontrado.")
    return vehicle


def _payload_hash(operation_type: str, payload: dict) -> str:
    raw = json.dumps(
        {"operation_type": operation_type, "payload": payload},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clean_operation_id(value) -> str:
    operation_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", operation_id):
        raise ValueError("Identificador da operacao mobile invalido.")
    return operation_id


def _work_order_guard(work_order, user) -> None:
    if not user_has_mechanic_workspace_access(user):
        raise MobileOperationAccessError("Acesso restrito a manutencao.")
    if user.tipo == "mecanico" and work_order.assigned_mechanic_user_id != user.id:
        raise MobileOperationAccessError("Esta OS esta atribuida a outro mecanico.")


def _maintenance_item_guard(item, user) -> None:
    if not user_has_mechanic_workspace_access(user):
        raise MobileOperationAccessError("Acesso restrito a manutencao.")
    if user.tipo != "mecanico":
        return
    schedule_mechanic_id = item.schedule.assigned_mechanic_user_id if item.schedule else None
    if item.assigned_mechanic_user_id not in {None, user.id} and schedule_mechanic_id not in {None, user.id}:
        raise MobileOperationAccessError("Esta manutencao nao foi direcionada para voce.")


def _run_operation(operation_type: str, payload: dict, user):
    if operation_type == "HORIMETRO":
        vehicle_id = int(payload.get("vehicle_id") or 0)
        return {"hourmeter": record_hourmeter(vehicle_id, payload, user.id).to_dict(), "vehicle_id": vehicle_id}
    if operation_type == "EMERGENCIA":
        emergency = create_emergency(payload, user.id)
        return {"emergency": emergency.to_dict(), "vehicle_id": emergency.vehicle_id}
    if operation_type == "MANUTENCAO_ATUALIZAR_ITEM":
        item_id = int(payload.get("maintenance_item_id") or 0)
        item = db.session.get(MaintenanceScheduleItem, item_id)
        if not item:
            raise LookupError("Item de manutencao nao encontrado.")
        _maintenance_item_guard(item, user)
        status = str(payload.get("status") or "").strip().upper()
        if status not in {"INSTALADO", "NAO_EXECUTADO"}:
            raise ValueError("A operacao mobile permite apenas instalar ou marcar como nao executado.")
        item = update_schedule_item(
            item_id,
            {
                "status": status,
                "observation": payload.get("observation"),
                "not_executed_reason": payload.get("not_executed_reason"),
                "photo_after": payload.get("photo_after"),
            },
            user=user,
        )
        return {"maintenance_item": item.to_dict(), "vehicle_id": item.vehicle_id}

    work_order_id = int(payload.get("work_order_id") or 0)
    work_order = get_work_order(work_order_id)
    _work_order_guard(work_order, user)
    if operation_type == "OS_INICIAR":
        work_order = start_work_order(work_order_id, payload)
    elif operation_type == "OS_CONCLUIR":
        work_order = complete_repair(work_order_id, payload)
    elif operation_type == "OS_TESTAR":
        work_order = record_operational_test(work_order_id, payload)
    elif operation_type == "OS_LIBERAR":
        work_order = release_work_order(work_order_id, user.id)
    else:  # Defensive guard: this function is only called after type validation.
        raise ValueError("Tipo de operacao mobile invalido.")
    return {"work_order": work_order.to_dict(), "vehicle_id": work_order.vehicle_id}


def sync_mobile_operation(request_payload: dict, user) -> dict:
    operation_type = str(request_payload.get("operation_type") or "").strip().upper()
    if operation_type not in MOBILE_OPERATION_TYPES:
        raise ValueError("Tipo de operacao mobile invalido.")
    operation_id = _clean_operation_id(request_payload.get("operation_id"))
    payload = request_payload.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Dados da operacao mobile invalidos.")

    payload_hash = _payload_hash(operation_type, payload)
    occurred_at = parse_datetime(request_payload.get("occurred_at"), field_name="Data da operacao mobile")
    existing = MobileSyncOperation.query.filter_by(operation_id=operation_id).first()
    if existing:
        if existing.user_id != user.id or existing.payload_hash != payload_hash or existing.operation_type != operation_type:
            raise MobileOperationConflict("Este identificador ja foi usado por outra operacao.")
        if existing.status == "APLICADA":
            return {
                "operation_id": existing.operation_id,
                "status": existing.status,
                "replayed": True,
                "result": json.loads(existing.result_json or "{}"),
            }
        raise MobileOperationConflict(existing.conflict_reason or "A operacao precisa de revisao antes de novo envio.")

    vehicle_id = payload.get("vehicle_id")
    operation = MobileSyncOperation(
        operation_id=operation_id,
        operation_type=operation_type,
        vehicle_id=int(vehicle_id) if str(vehicle_id or "").isdigit() else None,
        user_id=user.id,
        payload_hash=payload_hash,
        occurred_at=occurred_at,
    )
    db.session.add(operation)
    db.session.commit()

    try:
        result = _run_operation(operation_type, payload, user)
    except MobileOperationAccessError:
        db.session.rollback()
        db.session.delete(operation)
        db.session.commit()
        raise
    except (LookupError, ValueError) as exc:
        db.session.rollback()
        operation = db.session.get(MobileSyncOperation, operation.id)
        operation.status = "CONFLITO"
        operation.conflict_reason = str(exc)
        operation.processed_at = now_manaus_naive()
        db.session.commit()
        raise MobileOperationConflict(str(exc)) from exc

    operation = db.session.get(MobileSyncOperation, operation.id)
    operation.status = "APLICADA"
    operation.result_json = json.dumps(result, ensure_ascii=True, default=str)
    operation.processed_at = now_manaus_naive()
    db.session.commit()
    return {"operation_id": operation.operation_id, "status": operation.status, "replayed": False, "result": result}
