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
        return ""

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)

    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


def _csv_env(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in (os.getenv(name) or "").split(",") if item.strip())


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _non_negative_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um numero inteiro nao negativo.") from exc
    if value < 0:
        raise RuntimeError(f"{name} deve ser um numero inteiro nao negativo.")
    return value


def _is_sqlite_url(url: str) -> bool:
    return url.lower().startswith("sqlite:")


class Config:
    APP_ENV = (os.getenv("CHECKLIST_ENV") or "development").strip().lower()
    ALLOW_SQLITE = _bool_env("CHECKLIST_ALLOW_SQLITE", default=APP_ENV == "test")
    LEGACY_LOCAL_BOOTSTRAP_ENABLED = _bool_env(
        "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP",
        default=APP_ENV == "test",
    )
    SECRET_KEY = os.getenv("SECRET_KEY", "checklist-frota-dev-secret")
    RAW_DATABASE_URL = (
        None if os.getenv("CHECKLIST_FORCE_LOCAL_DB") == "1" else os.getenv("DATABASE_URL")
    )
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        RAW_DATABASE_URL
        or (f"sqlite:///{DATA_ROOT / 'checklist_frota.db'}" if ALLOW_SQLITE else None)
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "15000"))
    SQLITE_JOURNAL_MODE = (os.getenv("SQLITE_JOURNAL_MODE") or "WAL").strip().upper()
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024
    TOKEN_MAX_AGE_SECONDS = int(os.getenv("TOKEN_MAX_AGE_SECONDS", "28800"))
    CORS_STRICT_MODE = _bool_env("CORS_STRICT_MODE", default=True)
    CORS_ALLOWED_ORIGINS = tuple(
        dict.fromkeys(
            _csv_env("CORS_ALLOWED_ORIGINS")
            + (
                "https://checklist-web-uej3.onrender.com",
                "http://127.0.0.1:5500",
                "http://localhost:5500",
                # Permite o Web Mobile aberto em celular/tablet na mesma rede
                # privada do computador, sem liberar origens externas.
                r"^http://(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}):5500$",
            )
        )
    )
    INITIAL_ADMIN_LOGIN = (os.getenv("INITIAL_ADMIN_LOGIN") or "").strip()
    INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD") or ""
    INITIAL_ADMIN_NAME = (os.getenv("INITIAL_ADMIN_NAME") or "Administrador").strip()
    AUTOMATION_JOB_TOKEN = os.getenv("AUTOMATION_JOB_TOKEN")
    UPLOAD_FOLDER = DATA_ROOT / "uploads"
    BACKUP_FOLDER = Path(os.getenv("BACKUP_FOLDER", DATA_ROOT / "backups"))
    BACKUP_RETENTION_COUNT = _non_negative_int_env("BACKUP_RETENTION_COUNT", default=30)
    BACKUP_EXTERNAL_FOLDER = (os.getenv("BACKUP_EXTERNAL_FOLDER") or "").strip()
    INVENTORY_FILE = os.getenv("INVENTORY_FILE")
    WASH_CONTROL_FILE = os.getenv("WASH_CONTROL_FILE")
    PORTUARY_ONLY_MODE = _bool_env("PORTUARY_ONLY_MODE", default=False)
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "evidencias")
    FREE_DB_LIMIT_MB = int(os.getenv("FREE_DB_LIMIT_MB", "500"))
    FREE_STORAGE_LIMIT_MB = int(os.getenv("FREE_STORAGE_LIMIT_MB", "1024"))

    @classmethod
    def validate_environment(cls) -> None:
        """Reject implicit local databases in official application profiles."""
        if cls.APP_ENV not in {"development", "test", "production"}:
            raise RuntimeError("CHECKLIST_ENV deve ser development, test ou production.")
        if cls.APP_ENV == "test" and os.getenv("CHECKLIST_FORCE_LOCAL_DB") == "1":
            raise RuntimeError(
                "CHECKLIST_FORCE_LOCAL_DB nao pode ser usado em testes; cada teste deve usar seu SQLite temporario."
            )
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError(
                "DATABASE_URL e obrigatoria. SQLite temporario exige CHECKLIST_ALLOW_SQLITE=1."
            )
        if _is_sqlite_url(cls.SQLALCHEMY_DATABASE_URI) and not cls.ALLOW_SQLITE:
            raise RuntimeError(
                "SQLite nao e permitido neste ambiente. Use PostgreSQL ou defina "
                "CHECKLIST_ALLOW_SQLITE=1 somente para ambiente local controlado."
            )
        if cls.LEGACY_LOCAL_BOOTSTRAP_ENABLED and not _is_sqlite_url(cls.SQLALCHEMY_DATABASE_URI):
            raise RuntimeError(
                "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP somente pode ser usado com SQLite temporario."
            )
        if _is_sqlite_url(cls.SQLALCHEMY_DATABASE_URI):
            if cls.SQLITE_BUSY_TIMEOUT_MS < 1000:
                raise RuntimeError("SQLITE_BUSY_TIMEOUT_MS deve ser de pelo menos 1000 milissegundos.")
            if cls.SQLITE_JOURNAL_MODE not in {"WAL", "DELETE"}:
                raise RuntimeError("SQLITE_JOURNAL_MODE deve ser WAL ou DELETE.")
