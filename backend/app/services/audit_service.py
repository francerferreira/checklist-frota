from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flask import g, has_request_context, request
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.user import User

_AUDIT_HOOKS_REGISTERED = False
_SENSITIVE_FIELDS = {"senha_hash", "password", "password_hash", "token"}
_IGNORED_UPDATE_FIELDS = {"updated_at"}
_MAX_AUDIT_VALUE_LEN = 5000


def _to_entity_type(instance: Any) -> str:
    name = instance.__class__.__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


def _safe_current_user_id() -> int | None:
    if not has_request_context():
        return None
    current = getattr(g, "current_user", None)
    return getattr(current, "id", None)


def _safe_serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _redact_field(field_name: str, value: Any) -> Any:
    if field_name in _SENSITIVE_FIELDS:
        return "[REDACTED]"
    return _safe_serialize(value)


def _truncate_text(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= _MAX_AUDIT_VALUE_LEN:
        return value
    return f"{value[:_MAX_AUDIT_VALUE_LEN]}... [TRUNCATED]"


def _dump_json(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    return _truncate_text(json.dumps(payload, ensure_ascii=False, default=str))


def _is_auditable_instance(instance: Any) -> bool:
    if isinstance(instance, AuditLog):
        return False
    return hasattr(instance, "__table__")


def _snapshot_instance(instance: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    table = getattr(instance, "__table__", None)
    if table is None:
        return data
    for column in table.columns:
        name = column.name
        data[name] = _redact_field(name, getattr(instance, name, None))
    return data


def _collect_update_changes(instance: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    state = inspect(instance)
    old_payload: dict[str, Any] = {}
    new_payload: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        field_name = attr.key
        if field_name in _IGNORED_UPDATE_FIELDS:
            continue
        history = state.attrs[field_name].history
        if not history.has_changes():
            continue
        old_value = history.deleted[0] if history.deleted else None
        new_value = history.added[0] if history.added else getattr(instance, field_name, None)
        if old_value == new_value:
            continue
        old_payload[field_name] = _redact_field(field_name, old_value)
        new_payload[field_name] = _redact_field(field_name, new_value)
    return old_payload, new_payload


def _record_buffered_change(
    session: Session,
    *,
    instance: Any,
    action: str,
    old_payload: dict[str, Any] | None,
    new_payload: dict[str, Any] | None,
) -> None:
    buffer = session.info.setdefault("_audit_buffer", [])
    buffer.append(
        {
            "instance": instance,
            "action": action,
            "entity_type": _to_entity_type(instance),
            "entity_id": getattr(instance, "id", None),
            "user_id": _safe_current_user_id(),
            "old_value": _dump_json(old_payload),
            "new_value": _dump_json(new_payload),
        }
    )


def _before_flush(session: Session, flush_context, instances):  # noqa: ANN001
    if session.info.get("_audit_muted"):
        return
    if session.info.get("_audit_writing_logs"):
        return

    for instance in list(session.new):
        if not _is_auditable_instance(instance):
            continue
        _record_buffered_change(
            session,
            instance=instance,
            action="CREATE",
            old_payload=None,
            new_payload=_snapshot_instance(instance),
        )

    for instance in list(session.dirty):
        if not _is_auditable_instance(instance):
            continue
        if not session.is_modified(instance, include_collections=False):
            continue
        old_payload, new_payload = _collect_update_changes(instance)
        if not old_payload and not new_payload:
            continue
        _record_buffered_change(
            session,
            instance=instance,
            action="UPDATE",
            old_payload=old_payload,
            new_payload=new_payload,
        )

    for instance in list(session.deleted):
        if not _is_auditable_instance(instance):
            continue
        _record_buffered_change(
            session,
            instance=instance,
            action="DELETE",
            old_payload=_snapshot_instance(instance),
            new_payload=None,
        )


def _after_flush_postexec(session: Session, flush_context):  # noqa: ANN001
    if session.info.get("_audit_writing_logs"):
        return
    buffer = session.info.pop("_audit_buffer", None) or []
    if not buffer:
        return

    logs: list[AuditLog] = []
    for entry in buffer:
        instance = entry.get("instance")
        entity_id = entry.get("entity_id")
        if entity_id is None and instance is not None:
            entity_id = getattr(instance, "id", None)
        if entity_id is None:
            entity_id = 0
        logs.append(
            AuditLog(
                user_id=entry.get("user_id"),
                entity_type=entry.get("entity_type") or "SYSTEM",
                entity_id=int(entity_id),
                action=entry.get("action") or "UPDATE",
                old_value=entry.get("old_value"),
                new_value=entry.get("new_value"),
            )
        )

    if not logs:
        return

    session.info["_audit_writing_logs"] = True
    try:
        session.add_all(logs)
    finally:
        session.info.pop("_audit_writing_logs", None)


def install_audit_hooks() -> None:
    global _AUDIT_HOOKS_REGISTERED
    if _AUDIT_HOOKS_REGISTERED:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "after_flush_postexec", _after_flush_postexec)
    _AUDIT_HOOKS_REGISTERED = True


def record_event(
    *,
    user_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    old_value: Any = None,
    new_value: Any = None,
) -> None:
    log = AuditLog(
        user_id=user_id,
        entity_type=str(entity_type or "SYSTEM").upper(),
        entity_id=int(entity_id or 0),
        action=str(action or "EVENT").upper(),
        old_value=_truncate_text(str(old_value)) if old_value is not None else None,
        new_value=_truncate_text(str(new_value)) if new_value is not None else None,
    )
    db.session.add(log)


def record_status_change(user_id: int, entity_type: str, entity_id: int, old_status: str, new_status: str):
    if old_status == new_status:
        return
    record_event(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action="STATUS_CHANGE",
        old_value=str(old_status) if old_status else "N/A",
        new_value=str(new_status) if new_status else "N/A",
    )


def record_login_event(user: User, success: bool) -> None:
    payload = {
        "login": user.login,
        "nome": user.nome,
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.user_agent.string if request.user_agent else "",
    }
    record_event(
        user_id=user.id if success else None,
        entity_type="SESSION",
        entity_id=user.id or 0,
        action="LOGIN_SUCCESS" if success else "LOGIN_FAILED",
        new_value=json.dumps(payload, ensure_ascii=False),
    )


def record_logout_event(user: User | None) -> None:
    payload = {
        "login": getattr(user, "login", None),
        "nome": getattr(user, "nome", None),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.user_agent.string if request.user_agent else "",
    }
    record_event(
        user_id=getattr(user, "id", None),
        entity_type="SESSION",
        entity_id=getattr(user, "id", 0) or 0,
        action="LOGOUT",
        new_value=json.dumps(payload, ensure_ascii=False),
    )
