from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import requests
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _slugify(value: str) -> str:
    sanitized = secure_filename((value or "").strip().lower())
    return sanitized or "arquivo"


def storage_backend() -> str:
    if (
        current_app.config.get("STORAGE_BACKEND") == "supabase"
        and current_app.config.get("SUPABASE_URL")
        and current_app.config.get("SUPABASE_SERVICE_ROLE_KEY")
    ):
        return "supabase"
    return "local"


def _headers(content_type: str | None = None) -> dict[str, str]:
    token = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {
        "apikey": token,
        "Authorization": f"Bearer {token}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _storage_url(path: str) -> str:
    base_url = current_app.config["SUPABASE_URL"]
    return f"{base_url}/storage/v1/{path.lstrip('/')}"


def _bucket() -> str:
    return current_app.config["SUPABASE_STORAGE_BUCKET"]


def build_filename(file_storage: FileStorage, vehicle: str, item: str, user: str) -> str:
    original_name = secure_filename(file_storage.filename or "")
    extension = Path(original_name).suffix.lower() or ".jpg"
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato de imagem nao suportado.")

    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
    return f"{_slugify(vehicle)}_{_slugify(item)}_{_slugify(user)}_{timestamp}{extension}"


def save_local_upload(
    file_storage: FileStorage,
    upload_folder: Path,
    vehicle: str,
    item: str,
    user: str,
) -> str:
    filename = build_filename(file_storage, vehicle, item, user)
    upload_folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(upload_folder / filename)
    return filename


def save_supabase_upload(file_storage: FileStorage, vehicle: str, item: str, user: str) -> str:
    filename = build_filename(file_storage, vehicle, item, user)
    object_path = f"{datetime.utcnow():%Y/%m/%d}/{filename}"
    data = file_storage.read()
    content_type = file_storage.mimetype or "application/octet-stream"
    response = requests.post(
        _storage_url(f"object/{_bucket()}/{quote(object_path)}"),
        headers={
            **_headers(content_type),
            "x-upsert": "false",
            "cache-control": "3600",
        },
        data=data,
        timeout=60,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao enviar arquivo para Supabase Storage: {response.text[:180]}")
    return object_path


def download_supabase_object(object_path: str) -> tuple[bytes, str]:
    response = requests.get(
        _storage_url(f"object/{_bucket()}/{quote(object_path)}"),
        headers=_headers(),
        timeout=60,
    )
    if response.status_code >= 400:
        raise FileNotFoundError(object_path)
    return response.content, response.headers.get("Content-Type", "application/octet-stream")


def delete_supabase_objects(object_paths: list[str]) -> int:
    if not object_paths:
        return 0
    response = requests.delete(
        _storage_url(f"object/{_bucket()}"),
        headers=_headers("application/json"),
        json={"prefixes": object_paths},
        timeout=60,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao limpar arquivos no Supabase Storage: {response.text[:180]}")
    return len(object_paths)


def _list_supabase_page(prefix: str, offset: int) -> list[dict[str, Any]]:
    response = requests.post(
        _storage_url(f"object/list/{_bucket()}"),
        headers=_headers("application/json"),
        json={
            "prefix": prefix,
            "limit": 100,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        },
        timeout=60,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao listar Supabase Storage: {response.text[:180]}")
    return response.json() or []


def list_supabase_objects(prefix: str = "") -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    offset = 0
    while True:
        rows = _list_supabase_page(prefix, offset)
        if not rows:
            break
        for row in rows:
            name = row.get("name") or ""
            full_path = f"{prefix.rstrip('/')}/{name}".strip("/")
            metadata = row.get("metadata") or {}
            if row.get("id") is None and not metadata:
                objects.extend(list_supabase_objects(full_path))
            else:
                row["path"] = full_path
                row["size"] = int(metadata.get("size") or 0)
                objects.append(row)
        if len(rows) < 100:
            break
        offset += len(rows)
    return objects


def local_storage_objects(upload_folder: Path) -> list[dict[str, Any]]:
    if not upload_folder.exists():
        return []
    rows = []
    for path in upload_folder.rglob("*"):
        if path.is_file():
            rows.append(
                {
                    "path": path.relative_to(upload_folder).as_posix(),
                    "size": path.stat().st_size,
                    "updated_at": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat(),
                }
            )
    return rows


def storage_objects() -> list[dict[str, Any]]:
    if storage_backend() == "supabase":
        return list_supabase_objects()
    return local_storage_objects(Path(current_app.config["UPLOAD_FOLDER"]))


def storage_usage_bytes() -> int:
    return sum(int(item.get("size") or 0) for item in storage_objects())


def path_to_supabase_object(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    marker = "/uploads/supabase/"
    if marker in text:
        return unquote(text.split(marker, 1)[1])
    public_marker = f"/storage/v1/object/public/{_bucket()}/"
    private_marker = f"/storage/v1/object/{_bucket()}/"
    for item in (public_marker, private_marker):
        if item in text:
            return unquote(text.split(item, 1)[1])
    return None
