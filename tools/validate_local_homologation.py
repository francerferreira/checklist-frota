from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class HomologationValidationError(RuntimeError):
    pass


def _sqlite_check(engine) -> dict:
    with engine.connect() as connection:
        integrity = str(connection.execute(text("PRAGMA integrity_check")).scalar_one())
        foreign_key_violations = connection.execute(text("PRAGMA foreign_key_check")).all()
    if integrity.lower() != "ok":
        raise HomologationValidationError(f"Falha de integridade SQLite: {integrity}")
    if foreign_key_violations:
        raise HomologationValidationError(
            f"Foram encontradas {len(foreign_key_violations)} violacoes de chave estrangeira."
        )
    return {"integrity": integrity, "foreign_key_violations": 0}


def run_local_homologation(app) -> dict:
    """Valida um SQLite local sem tocar em PostgreSQL ou em dados de producao."""
    from app.extensions import db
    from app.services.backup_service import create_backup
    from tools.restore_backup_archive import restore_backup, validate_backup

    if db.engine.dialect.name != "sqlite":
        raise HomologationValidationError(
            "Este verificador e exclusivo para SQLite local. PostgreSQL exige homologacao separada."
        )

    database_path = db.engine.url.database
    if not database_path or database_path == ":memory:":
        raise HomologationValidationError("Informe um arquivo SQLite local; banco em memoria nao pode ser homologado.")

    health = app.test_client().get("/health")
    if health.status_code != 200:
        raise HomologationValidationError(f"Health check falhou com HTTP {health.status_code}.")

    source_check = _sqlite_check(db.engine)
    source_tables = len(inspect(db.engine).get_table_names())
    backup = create_backup()
    backup_path = Path(backup["path"])
    archive = validate_backup(backup_path)
    restore_directory = Path(tempfile.mkdtemp(prefix="checklist-frota-restore-"))
    try:
        restored = restore_backup(backup_path, restore_directory, db.metadata)
        restored_engine = create_engine(f"sqlite:///{restored['database_path']}")
        try:
            restored_check = _sqlite_check(restored_engine)
            restored_tables = len(inspect(restored_engine).get_table_names())
        finally:
            restored_engine.dispose()
    finally:
        shutil.rmtree(restore_directory, ignore_errors=True)

    return {
        "ready": True,
        "health": health.get_json(),
        "source": {"path": str(database_path), "tables": source_tables, **source_check},
        "backup": {
            "filename": backup["filename"],
            "size_bytes": backup["size_bytes"],
            "tables": archive["tables"],
            "rows": archive["rows"],
            "photos": archive["photos"],
        },
        "restore": {
            "tables": restored_tables,
            "rows": restored["rows"],
            "photos": restored["photos"],
            **restored_check,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida a prontidao de homologacao do SQLite local.")
    parser.add_argument("--report", type=Path, help="Arquivo JSON opcional para registrar o resultado.")
    args = parser.parse_args(argv)

    from app import create_app

    try:
        app = create_app()
        with app.app_context():
            result = run_local_homologation(app)
        payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0
    except (HomologationValidationError, OSError, ValueError) as exc:
        print(f"Homologacao local nao aprovada: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
