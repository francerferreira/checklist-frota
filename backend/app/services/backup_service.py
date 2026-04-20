from __future__ import annotations

import json
import os
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import select, text

from app.extensions import db
from app.models import Activity, Checklist, ChecklistItem, MaterialMovement, WashRecord
from app.services.storage_service import (
    delete_supabase_objects,
    download_supabase_object,
    path_to_supabase_object,
    storage_backend,
    storage_objects,
    storage_usage_bytes,
)


CLEANUP_CONFIRMATION = "LIMPAR_DADOS_ANTIGOS"
PHOTO_COLUMNS = ("foto_path", "foto_antes", "foto_depois")


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _mb(value: int) -> float:
    return round(value / 1024 / 1024, 2)


def backup_folder() -> Path:
    folder = Path(current_app.config["BACKUP_FOLDER"])
    if not folder.is_absolute():
        folder = Path(current_app.root_path).parents[1] / folder
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def database_usage_bytes() -> int:
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        path = Path(uri.replace("sqlite:///", "", 1))
        return path.stat().st_size if path.exists() else 0
    try:
        return int(db.session.execute(text("select pg_database_size(current_database())")).scalar() or 0)
    except Exception:
        return 0


def storage_status() -> dict:
    db_bytes = database_usage_bytes()
    file_bytes = storage_usage_bytes()
    db_limit = int(current_app.config["FREE_DB_LIMIT_MB"]) * 1024 * 1024
    storage_limit = int(current_app.config["FREE_STORAGE_LIMIT_MB"]) * 1024 * 1024

    def section(used: int, limit: int) -> dict:
        percent = round((used / limit) * 100, 2) if limit else 0
        if percent >= 95:
            level = "critico"
        elif percent >= 85:
            level = "vermelho"
        elif percent >= 70:
            level = "amarelo"
        else:
            level = "ok"
        return {
            "used_bytes": used,
            "used_mb": _mb(used),
            "limit_bytes": limit,
            "limit_mb": _mb(limit),
            "percent": percent,
            "level": level,
        }

    return {
        "database": section(db_bytes, db_limit),
        "storage": section(file_bytes, storage_limit),
        "storage_backend": storage_backend(),
        "generated_at": datetime.utcnow().isoformat(),
    }


def _all_table_rows() -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {}
    for table in db.metadata.sorted_tables:
        rows = db.session.execute(select(table)).mappings().all()
        data[table.name] = [dict(row) for row in rows]
    return data


def _write_database_json(zip_file: zipfile.ZipFile, rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
    for table_name, rows in rows_by_table.items():
        payload = json.dumps(rows, ensure_ascii=False, indent=2, default=_json_default)
        zip_file.writestr(f"banco/{table_name}.json", payload)


def _write_storage_files(zip_file: zipfile.ZipFile) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    if storage_backend() == "supabase":
        for item in storage_objects():
            object_path = item["path"]
            try:
                content, content_type = download_supabase_object(object_path)
            except FileNotFoundError:
                continue
            zip_file.writestr(f"fotos/{object_path}", content)
            manifest.append(
                {
                    "path": object_path,
                    "size": len(content),
                    "content_type": content_type,
                    "storage": "supabase",
                }
            )
        return manifest

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    if not upload_folder.exists():
        return manifest
    for path in upload_folder.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(upload_folder).as_posix()
        zip_file.write(path, f"fotos/{relative_path}")
        manifest.append(
            {
                "path": relative_path,
                "size": path.stat().st_size,
                "storage": "local",
            }
        )
    return manifest


def create_backup() -> dict:
    now = datetime.utcnow()
    filename = f"backup-checklist-{now:%Y%m%d-%H%M%S}.zip"
    path = backup_folder() / filename
    rows_by_table = _all_table_rows()
    status = storage_status()

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        _write_database_json(zip_file, rows_by_table)
        photos = _write_storage_files(zip_file)
        manifest = {
            "name": filename,
            "generated_at": now.isoformat(),
            "storage_status": status,
            "tables": {name: len(rows) for name, rows in rows_by_table.items()},
            "photos": photos,
            "cleanup_confirmation_required": CLEANUP_CONFIRMATION,
        }
        zip_file.writestr("backup_manifesto.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zip_file.writestr(
            "restauracao/instrucoes.txt",
            "Backup completo do Checklist Live. Guarde este arquivo fora da nuvem antes de limpar dados antigos.",
        )

    return {
        "filename": filename,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "size_mb": _mb(path.stat().st_size),
        "download_url": f"/admin/backups/{filename}/download",
        "storage_status": status,
    }


def _photo_references_from_rows(rows: list[Any]) -> set[str]:
    refs: set[str] = set()
    for row in rows:
        for column in PHOTO_COLUMNS:
            value = getattr(row, column, None)
            if value:
                refs.add(str(value))
    return refs


def _all_remaining_photo_refs() -> set[str]:
    refs: set[str] = set()
    tables = [
        ("checklist_items", "foto_antes"),
        ("checklist_items", "foto_depois"),
        ("activity_items", "foto_antes"),
        ("activity_items", "foto_depois"),
        ("mechanic_non_conformities", "foto_antes"),
        ("mechanic_non_conformities", "foto_depois"),
        ("wash_records", "foto_path"),
        ("vehicles", "foto_path"),
        ("materials", "foto_path"),
        ("checklist_catalog_items", "foto_path"),
    ]
    for table_name, column_name in tables:
        try:
            values = db.session.execute(text(f"select {column_name} from {table_name} where {column_name} is not null")).all()
        except Exception:
            continue
        refs.update(str(row[0]) for row in values if row[0])
    return refs


def _delete_photo_refs(refs: set[str]) -> int:
    remaining_refs = _all_remaining_photo_refs()
    stale_refs = refs - remaining_refs
    if storage_backend() == "supabase":
        object_paths = sorted({path for ref in stale_refs if (path := path_to_supabase_object(ref))})
        return delete_supabase_objects(object_paths)

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    deleted = 0
    for ref in stale_refs:
        if not ref.startswith("/uploads/"):
            continue
        filename = ref.split("/uploads/", 1)[1]
        path = upload_folder / filename
        if path.exists() and path.is_file():
            path.unlink()
            deleted += 1
    return deleted


def cleanup_old_records(
    *,
    keep_days: int = 14,
    backup_filename: str | None = None,
    confirmation: str | None = None,
    dry_run: bool = True,
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=max(1, keep_days))
    old_checklists = Checklist.query.filter(Checklist.created_at < cutoff).all()
    old_washes = WashRecord.query.filter(WashRecord.created_at < cutoff).all()
    old_activities = Activity.query.filter(
        Activity.status == "FINALIZADA",
        Activity.finalized_at.isnot(None),
        Activity.finalized_at < cutoff,
    ).all()

    photo_refs = set()
    checklist_item_ids: list[int] = []
    activity_ids: list[int] = []

    for checklist in old_checklists:
        for item in checklist.items:
            checklist_item_ids.append(item.id)
            photo_refs.update(_photo_references_from_rows([item]))
    photo_refs.update(_photo_references_from_rows(old_washes))
    for activity in old_activities:
        activity_ids.append(activity.id)
        photo_refs.update(_photo_references_from_rows(list(activity.items)))

    result = {
        "dry_run": dry_run,
        "cutoff": cutoff.isoformat(),
        "keep_days": keep_days,
        "checklists": len(old_checklists),
        "lavagens": len(old_washes),
        "atividades_finalizadas": len(old_activities),
        "fotos_candidatas": len(photo_refs),
        "confirmation_required": CLEANUP_CONFIRMATION,
    }
    if dry_run:
        return result

    if confirmation != CLEANUP_CONFIRMATION:
        raise ValueError(f"Confirmacao obrigatoria: {CLEANUP_CONFIRMATION}")
    if not backup_filename:
        raise ValueError("Informe o arquivo de backup antes de limpar dados antigos.")
    backup_path = backup_folder() / Path(backup_filename).name
    if not backup_path.exists():
        raise ValueError("Backup informado nao existe no servidor.")

    if checklist_item_ids:
        MaterialMovement.query.filter(MaterialMovement.checklist_item_id.in_(checklist_item_ids)).update(
            {MaterialMovement.checklist_item_id: None},
            synchronize_session=False,
        )
    if activity_ids:
        MaterialMovement.query.filter(MaterialMovement.activity_id.in_(activity_ids)).update(
            {MaterialMovement.activity_id: None},
            synchronize_session=False,
        )
    for checklist in old_checklists:
        db.session.delete(checklist)
    for wash in old_washes:
        db.session.delete(wash)
    for activity in old_activities:
        db.session.delete(activity)
    db.session.commit()

    try:
        result["fotos_removidas"] = _delete_photo_refs(photo_refs)
    except Exception as exc:
        result["fotos_removidas"] = 0
        result["foto_cleanup_error"] = str(exc)
    return result


def safe_backup_path(filename: str) -> Path:
    path = backup_folder() / Path(filename).name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(filename)
    return path
