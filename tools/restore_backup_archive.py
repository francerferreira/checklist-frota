from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import date, datetime, time
from pathlib import Path, PurePosixPath

from sqlalchemy import Date, DateTime, Time, create_engine, func, select, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class BackupValidationError(ValueError):
    pass


def _safe_archive_path(value: str) -> PurePosixPath:
    path = PurePosixPath(str(value).replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise BackupValidationError(f"Caminho inseguro no backup: {value}")
    return path


def validate_backup(backup_path: Path) -> dict:
    if not backup_path.exists() or not backup_path.is_file():
        raise BackupValidationError(f"Backup nao encontrado: {backup_path}")
    try:
        with zipfile.ZipFile(backup_path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise BackupValidationError(f"Falha de CRC no arquivo: {bad_member}")
            members = set(archive.namelist())
            if "backup_manifesto.json" not in members:
                raise BackupValidationError("Manifesto ausente no backup.")
            manifest = json.loads(archive.read("backup_manifesto.json"))
            tables = manifest.get("tables")
            if not isinstance(tables, dict):
                raise BackupValidationError("Lista de tabelas invalida no manifesto.")
            total_rows = 0
            for table_name, expected_count in tables.items():
                member = f"banco/{table_name}.json"
                if member not in members:
                    raise BackupValidationError(f"Dados ausentes para a tabela {table_name}.")
                rows = json.loads(archive.read(member))
                if not isinstance(rows, list):
                    raise BackupValidationError(f"Conteudo invalido para a tabela {table_name}.")
                if len(rows) != int(expected_count):
                    raise BackupValidationError(
                        f"Contagem divergente em {table_name}: manifesto={expected_count}, arquivo={len(rows)}."
                    )
                total_rows += len(rows)
            for photo in manifest.get("photos") or []:
                photo_path = _safe_archive_path(photo.get("path") or "")
                if f"fotos/{photo_path.as_posix()}" not in members:
                    raise BackupValidationError(f"Anexo ausente no ZIP: {photo_path}")
            return {
                "generated_at": manifest.get("generated_at"),
                "tables": len(tables),
                "rows": total_rows,
                "photos": len(manifest.get("photos") or []),
                "manifest": manifest,
            }
    except (zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise BackupValidationError(f"Backup invalido: {exc}") from exc


def _convert_value(column, value):
    if value is None or not isinstance(value, str):
        return value
    if isinstance(column.type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        return date.fromisoformat(value)
    if isinstance(column.type, Time):
        return time.fromisoformat(value)
    return value


def _load_rows(archive: zipfile.ZipFile, table) -> list[dict]:
    rows = json.loads(archive.read(f"banco/{table.name}.json"))
    column_names = {column.name for column in table.columns}
    converted = []
    for row in rows:
        extra_columns = set(row) - column_names
        if extra_columns:
            raise BackupValidationError(
                f"Colunas desconhecidas em {table.name}: {', '.join(sorted(extra_columns))}."
            )
        converted.append(
            {
                key: _convert_value(table.columns[key], value)
                for key, value in row.items()
            }
        )
    return converted


def restore_backup(backup_path: Path, target_directory: Path, metadata, *, overwrite: bool = False) -> dict:
    validation = validate_backup(backup_path)
    manifest_tables = set(validation["manifest"]["tables"])
    model_tables = {table.name for table in metadata.sorted_tables}
    unknown_tables = manifest_tables - model_tables
    if unknown_tables:
        raise BackupValidationError(
            "Tabelas do backup nao reconhecidas pelos models atuais: " + ", ".join(sorted(unknown_tables))
        )

    target_directory.mkdir(parents=True, exist_ok=True)
    database_path = target_directory / "checklist_frota_restaurado.db"
    temporary_path = target_directory / ".checklist_frota_restaurado.tmp.db"
    uploads_path = target_directory / "uploads"
    if database_path.exists() and not overwrite:
        raise BackupValidationError(f"Destino ja existe: {database_path}")
    if uploads_path.exists() and not overwrite:
        raise BackupValidationError(f"Pasta de anexos ja existe: {uploads_path}")
    if temporary_path.exists():
        temporary_path.unlink()

    engine = create_engine(f"sqlite:///{temporary_path}")
    restored_counts: dict[str, int] = {}
    try:
        metadata.create_all(engine)
        with zipfile.ZipFile(backup_path) as archive, engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys = OFF"))
            for table in metadata.sorted_tables:
                if table.name not in manifest_tables:
                    continue
                rows = _load_rows(archive, table)
                if rows:
                    connection.execute(table.insert(), rows)
                restored_counts[table.name] = len(rows)

        with engine.connect() as connection:
            for table_name, expected_count in restored_counts.items():
                table = metadata.tables[table_name]
                actual_count = int(connection.execute(select(func.count()).select_from(table)).scalar_one())
                if actual_count != expected_count:
                    raise BackupValidationError(
                        f"Restauracao incompleta em {table_name}: esperado={expected_count}, restaurado={actual_count}."
                    )
            connection.execute(text("PRAGMA foreign_keys = ON"))
            violations = connection.execute(text("PRAGMA foreign_key_check")).all()
            if violations:
                raise BackupValidationError(f"Foram encontradas {len(violations)} violacoes de chave estrangeira.")

        if uploads_path.exists() and overwrite:
            shutil.rmtree(uploads_path)
        uploads_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(backup_path) as archive:
            for photo in validation["manifest"].get("photos") or []:
                relative_path = _safe_archive_path(photo.get("path") or "")
                source_name = f"fotos/{relative_path.as_posix()}"
                destination = uploads_path.joinpath(*relative_path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(source_name) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)

        engine.dispose()
        if database_path.exists():
            database_path.unlink()
        os.replace(temporary_path, database_path)
        return {
            "database_path": str(database_path),
            "uploads_path": str(uploads_path),
            "tables": len(restored_counts),
            "rows": sum(restored_counts.values()),
            "photos": validation["photos"],
        }
    except Exception:
        engine.dispose()
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    finally:
        engine.dispose()


def _app_metadata():
    from app.extensions import db
    import app.models  # noqa: F401

    return db.metadata


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida ou restaura um backup ZIP em SQLite isolado.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--target-directory", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        validation = validate_backup(args.backup)
        print(
            "Backup valido: "
            f"tabelas={validation['tables']}, linhas={validation['rows']}, anexos={validation['photos']}."
        )
        if args.validate_only:
            return 0
        if not args.target_directory:
            raise BackupValidationError("Informe --target-directory para testar a restauracao.")
        result = restore_backup(args.backup, args.target_directory, _app_metadata(), overwrite=args.overwrite)
        print(
            "Restauracao isolada concluida: "
            f"tabelas={result['tables']}, linhas={result['rows']}, anexos={result['photos']}."
        )
        print(f"Banco restaurado: {result['database_path']}")
        return 0
    except (BackupValidationError, OSError) as exc:
        print(f"Falha na validacao/restauracao: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
