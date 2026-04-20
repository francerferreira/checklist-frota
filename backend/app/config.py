import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
    DATA_ROOT = APP_ROOT / "backend_data"
else:
    APP_ROOT = Path(__file__).resolve().parents[2]
    DATA_ROOT = Path(__file__).resolve().parents[1]

DATA_ROOT.mkdir(parents=True, exist_ok=True)


def _normalize_database_url(url: str | None) -> str:
    if not url:
        return f"sqlite:///{DATA_ROOT / 'checklist_frota.db'}"

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)

    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "checklist-frota-dev-secret")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024
    TOKEN_MAX_AGE_SECONDS = int(os.getenv("TOKEN_MAX_AGE_SECONDS", "28800"))
    UPLOAD_FOLDER = DATA_ROOT / "uploads"
    BACKUP_FOLDER = Path(os.getenv("BACKUP_FOLDER", DATA_ROOT / "backups"))
    INVENTORY_FILE = os.getenv("INVENTORY_FILE")
    WASH_CONTROL_FILE = os.getenv("WASH_CONTROL_FILE")
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "evidencias")
    FREE_DB_LIMIT_MB = int(os.getenv("FREE_DB_LIMIT_MB", "500"))
    FREE_STORAGE_LIMIT_MB = int(os.getenv("FREE_STORAGE_LIMIT_MB", "1024"))
