from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.sqltypes import Numeric, String


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _database_url(env_file: Path) -> str:
    load_dotenv(env_file)
    value = (os.getenv("DATABASE_URL") or "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL nao configurada.")
    if value.startswith("postgresql+psycopg://"):
        return value.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg2://", 1)
    return value


def _type_signature(column_type) -> tuple:
    affinity = column_type._type_affinity.__name__.upper()
    if isinstance(column_type, String):
        return affinity, column_type.length
    if isinstance(column_type, Numeric):
        return affinity, column_type.precision, column_type.scale
    return (affinity,)


def _database_foreign_keys(inspector, table_name: str) -> set[tuple]:
    return {
        (
            tuple(item.get("constrained_columns") or ()),
            item.get("referred_table"),
            tuple(item.get("referred_columns") or ()),
        )
        for item in inspector.get_foreign_keys(table_name)
    }


def _model_foreign_keys(table) -> set[tuple]:
    result = set()
    for constraint in table.foreign_key_constraints:
        elements = list(constraint.elements)
        result.add(
            (
                tuple(element.parent.name for element in elements),
                elements[0].column.table.name if elements else None,
                tuple(element.column.name for element in elements),
            )
        )
    return result


def _database_uniques(inspector, table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints(table_name)
        if item.get("column_names")
    }


def _model_uniques(table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _database_indexes(inspector, table_name: str) -> set[tuple]:
    return {
        (tuple(item.get("column_names") or ()), bool(item.get("unique")))
        for item in inspector.get_indexes(table_name)
        if item.get("column_names")
    }


def _model_indexes(table) -> set[tuple]:
    return {
        (tuple(column.name for column in index.columns), bool(index.unique))
        for index in table.indexes
    }


def _database_checks(inspector, table_name: str) -> set[str]:
    return {
        str(item.get("name"))
        for item in inspector.get_check_constraints(table_name)
        if item.get("name")
    }


def _model_checks(table) -> set[str]:
    return {
        str(constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }


def compare_schema(connection, metadata) -> dict:
    inspector = inspect(connection)
    database_tables = set(inspector.get_table_names())
    model_tables = {table.name for table in metadata.sorted_tables}
    comparable_database_tables = database_tables - {"alembic_version"}
    issues: list[dict] = []

    for table_name in sorted(comparable_database_tables - model_tables):
        issues.append({"category": "table_only_database", "table": table_name})
    for table_name in sorted(model_tables - comparable_database_tables):
        issues.append({"category": "table_only_models", "table": table_name})

    for table_name in sorted(comparable_database_tables & model_tables):
        table = metadata.tables[table_name]
        database_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        model_columns = {column.name: column for column in table.columns}

        for column_name in sorted(database_columns.keys() - model_columns.keys()):
            issues.append({"category": "column_only_database", "table": table_name, "column": column_name})
        for column_name in sorted(model_columns.keys() - database_columns.keys()):
            issues.append({"category": "column_only_models", "table": table_name, "column": column_name})

        for column_name in sorted(database_columns.keys() & model_columns.keys()):
            database_column = database_columns[column_name]
            model_column = model_columns[column_name]
            database_type = _type_signature(database_column["type"])
            model_type = _type_signature(model_column.type)
            if database_type != model_type:
                issues.append(
                    {
                        "category": "column_type",
                        "table": table_name,
                        "column": column_name,
                        "database": database_type,
                        "model": model_type,
                    }
                )
            if not model_column.primary_key and bool(database_column.get("nullable")) != bool(model_column.nullable):
                issues.append(
                    {
                        "category": "column_nullable",
                        "table": table_name,
                        "column": column_name,
                        "database": bool(database_column.get("nullable")),
                        "model": bool(model_column.nullable),
                    }
                )

        checks = (
            (
                "primary_key",
                tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ()),
                tuple(column.name for column in table.primary_key.columns),
            ),
            ("foreign_keys", _database_foreign_keys(inspector, table_name), _model_foreign_keys(table)),
            ("unique_constraints", _database_uniques(inspector, table_name), _model_uniques(table)),
            ("indexes", _database_indexes(inspector, table_name), _model_indexes(table)),
            ("check_constraints", _database_checks(inspector, table_name), _model_checks(table)),
        )
        for category, database_value, model_value in checks:
            if database_value != model_value:
                issues.append(
                    {
                        "category": category,
                        "table": table_name,
                        "database": sorted(database_value) if isinstance(database_value, set) else database_value,
                        "model": sorted(model_value) if isinstance(model_value, set) else model_value,
                    }
                )

    database_revisions: list[str] = []
    if "alembic_version" in database_tables:
        database_revisions = sorted(
            str(item) for item in connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        )

    return {
        "dialect": connection.dialect.name,
        "database_table_count": len(comparable_database_tables),
        "model_table_count": len(model_tables),
        "database_revisions": database_revisions,
        "issues": issues,
    }


def migration_heads(versions_folder: Path) -> list[str]:
    revisions: set[str] = set()
    dependencies: set[str] = set()
    for path in versions_folder.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        values[target.id] = ast.literal_eval(node.value)
        revision = values.get("revision")
        down_revision = values.get("down_revision")
        if revision:
            revisions.add(str(revision))
        if isinstance(down_revision, (tuple, list)):
            dependencies.update(str(item) for item in down_revision if item)
        elif down_revision:
            dependencies.add(str(down_revision))
    return sorted(revisions - dependencies)


def _print_report(report: dict) -> None:
    print(f"Tabelas no banco: {report['database_table_count']}")
    print(f"Tabelas nos models: {report['model_table_count']}")
    print("Revisao no banco: " + (", ".join(report["database_revisions"]) or "nao registrada"))
    print("Head das migrations: " + (", ".join(report["migration_heads"]) or "nao encontrado"))
    if not report["issues"]:
        print("Divergencias estruturais: nenhuma")
        return
    print(f"Divergencias estruturais: {len(report['issues'])}")
    for issue in report["issues"]:
        location = issue.get("table", "-")
        if issue.get("column"):
            location += f".{issue['column']}"
        details = {key: value for key, value in issue.items() if key not in {"category", "table", "column"}}
        suffix = f" | {details}" if details else ""
        print(f"- {issue['category']}: {location}{suffix}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compara o schema configurado com os models sem alterar o banco.")
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--json-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from app.extensions import db
    import app.models  # noqa: F401

    database_url = _database_url(args.env_file)
    parsed = urlparse(database_url)
    print(f"Destino: {parsed.hostname or 'SQLite local'} / {(parsed.path or '/').lstrip('/') or '-'}")

    engine = create_engine(database_url, connect_args={"connect_timeout": 15} if parsed.scheme.startswith("postgres") else {})
    try:
        with engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            elif connection.dialect.name == "sqlite":
                connection.execute(text("PRAGMA query_only = ON"))
            report = compare_schema(connection, db.metadata)
            report["migration_heads"] = migration_heads(PROJECT_ROOT / "migrations" / "versions")
            if report["database_revisions"] != report["migration_heads"]:
                report["issues"].append(
                    {
                        "category": "migration_revision",
                        "database": report["database_revisions"],
                        "model": report["migration_heads"],
                    }
                )
            _print_report(report)
            if args.json_output:
                args.json_output.parent.mkdir(parents=True, exist_ok=True)
                args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            connection.rollback()
            return 1 if report["issues"] else 0
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        print(f"Falha na comparacao read-only: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
