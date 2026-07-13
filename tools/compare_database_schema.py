from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _database_url() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    value = (os.getenv("DATABASE_URL") or "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL nao configurada.")
    if value.startswith("postgresql+psycopg://"):
        return value.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg2://", 1)
    return value


def main() -> int:
    from app.extensions import db
    import app.models  # noqa: F401

    database_url = _database_url()
    parsed = urlparse(database_url)
    print(f"Destino: {parsed.hostname or 'SQLite local'} / {(parsed.path or '/').lstrip('/') or '-'}")

    engine = create_engine(database_url, connect_args={"connect_timeout": 15} if parsed.scheme.startswith("postgres") else {})
    try:
        with engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            inspector = inspect(connection)
            database_tables = set(inspector.get_table_names())
            model_tables = {table.name for table in db.metadata.sorted_tables}

            only_database = sorted(database_tables - model_tables - {"alembic_version"})
            only_models = sorted(model_tables - database_tables)
            drift = []
            for table_name in sorted(database_tables & model_tables):
                database_columns = {column["name"] for column in inspector.get_columns(table_name)}
                model_columns = {column.name for column in db.metadata.tables[table_name].columns}
                missing = sorted(model_columns - database_columns)
                extra = sorted(database_columns - model_columns)
                if missing or extra:
                    drift.append((table_name, missing, extra))

            print(f"Tabelas no banco: {len(database_tables)}")
            print(f"Tabelas nos models: {len(model_tables)}")
            print("Somente no banco: " + (", ".join(only_database) or "nenhuma"))
            print("Somente nos models: " + (", ".join(only_models) or "nenhuma"))
            for table_name, missing, extra in drift:
                print(
                    f"Divergencia {table_name}: faltando no banco={missing or 'nenhuma'}; "
                    f"extra no banco={extra or 'nenhuma'}"
                )
            connection.rollback()
            return 1 if only_database or only_models or drift else 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
