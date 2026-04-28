from __future__ import annotations

from datetime import datetime
from flask import Blueprint, g, request, send_file

from app.models import AuditLog
from app.services.auth_service import auth_required
from app.services.backup_service import (
    cleanup_old_records,
    create_backup,
    safe_backup_path,
    storage_status,
)
from app.utils.responses import api_response

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _guard_admin_access():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente admin pode acessar administracao.", status_code=403)
    return None


@bp.get("/audit-logs")
@auth_required
def get_audit_logs():
    """Consulta os logs de auditoria com filtros (Ponto 3 do escopo)."""
    denied = _guard_admin_access()
    if denied:
        return denied

    entity_type = request.args.get("entidade")
    date_from = request.args.get("data_inicio")
    date_to = request.args.get("data_fim")

    query = AuditLog.query.order_by(AuditLog.created_at.desc())

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.upper())

    if date_from:
        try:
            query = query.filter(AuditLog.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            return api_response(False, error="Data inicial inválida. Use o formato YYYY-MM-DD.", status_code=400)

    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to)
            if len(date_to.strip()) <= 10:
                parsed_to = parsed_to.replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.created_at <= parsed_to)
        except ValueError:
            return api_response(False, error="Data final inválida. Use o formato YYYY-MM-DD.", status_code=400)

    logs = query.limit(500).all()
    return api_response(True, data=[log.to_dict() for log in logs])


@bp.get("/storage/status")
@auth_required
def get_storage_status():
    denied = _guard_admin_access()
    if denied:
        return denied
    return api_response(True, data=storage_status())


@bp.post("/backups/create")
@auth_required
def create_backup_route():
    denied = _guard_admin_access()
    if denied:
        return denied
    try:
        return api_response(True, data=create_backup(), status_code=201)
    except RuntimeError as exc:
        return api_response(False, error=str(exc), status_code=502)


@bp.get("/backups/<path:filename>/download")
@auth_required
def download_backup_route(filename: str):
    denied = _guard_admin_access()
    if denied:
        return denied
    try:
        path = safe_backup_path(filename)
    except FileNotFoundError:
        return api_response(False, error="Backup nao encontrado.", status_code=404)
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.post("/cleanup/old-records")
@auth_required
def cleanup_old_records_route():
    denied = _guard_admin_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    keep_days = int(payload.get("keep_days") or 14)
    dry_run = bool(payload.get("dry_run", True))
    try:
        result = cleanup_old_records(
            keep_days=keep_days,
            backup_filename=payload.get("backup_filename"),
            confirmation=payload.get("confirmation"),
            dry_run=dry_run,
        )
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=result)
