from __future__ import annotations

from pathlib import Path

from werkzeug.datastructures import FileStorage

from app.services.storage_service import save_local_upload


def save_upload(
    file_storage: FileStorage,
    upload_folder: Path,
    vehicle: str,
    item: str,
    user: str,
) -> str:
    return save_local_upload(file_storage, upload_folder, vehicle, item, user)
