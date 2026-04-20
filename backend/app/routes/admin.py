from __future__ import annotations

from flask import Blueprint, g, jsonify, request, send_file

from app.services.auth_service import auth_required
from app.services.backup_service import (
    cleanup_old_records,
    create_backup,
    safe_backup_path,
    storage_status,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _guard_admin_access():
    if g.current_user.tipo != "admin":
        return jsonify({"error": "Somente admin pode acessar administracao."}), 403
    return None


@bp.get("/storage/status")
@auth_required
def get_storage_status():
    denied = _guard_admin_access()
    if denied:
        return denied
    return jsonify(storage_status())


@bp.post("/backups/create")
@auth_required
def create_backup_route():
    denied = _guard_admin_access()
    if denied:
        return denied
    try:
        return jsonify(create_backup()), 201
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502


@bp.get("/backups/<path:filename>/download")
@auth_required
def download_backup_route(filename: str):
    denied = _guard_admin_access()
    if denied:
        return denied
    try:
        path = safe_backup_path(filename)
    except FileNotFoundError:
        return jsonify({"error": "Backup nao encontrado."}), 404
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
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)
