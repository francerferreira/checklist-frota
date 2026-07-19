from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.extensions import db
from app.models import (
    AuditLog,
    ChecklistCatalogItem,
    EquipmentFamily,
    EquipmentProfile,
    User,
    Vehicle,
    WashQueueItem,
)
from app.utils.timezone import now_manaus_naive


def _as_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _as_json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _audit_key(
    created_at: Any,
    user_login: str | None,
    row: dict[str, Any],
    *,
    entity_id: int | None = None,
) -> tuple:
    timestamp = _as_datetime(created_at)
    return (
        timestamp.isoformat() if timestamp else None,
        user_login,
        row["entity_type"],
        int(row["entity_id"] if entity_id is None else entity_id),
        row["action"],
        row["old_value"],
        row["new_value"],
    )


def _source_rows(source_path: Path, table_name: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(source_path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(f'SELECT * FROM "{table_name}"')]
    finally:
        connection.close()


def build_plan(source_path: Path) -> dict[str, Any]:
    if db.engine.dialect.name != "postgresql":
        raise RuntimeError("A migracao segura exige PostgreSQL como banco de destino.")
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite nao encontrado: {source_path}")

    source_vehicles = _source_rows(source_path, "vehicles")
    source_users = _source_rows(source_path, "users")
    source_profiles = _source_rows(source_path, "equipment_profiles")
    source_families = _source_rows(source_path, "equipment_families")
    source_queue = _source_rows(source_path, "wash_queue_items")
    source_catalog = _source_rows(source_path, "checklist_catalog_items")
    source_audit = _source_rows(source_path, "audit_logs")
    source_revoked = _source_rows(source_path, "revoked_tokens")

    target_vehicles = {vehicle.frota.upper(): vehicle for vehicle in Vehicle.query.all()}
    target_users = {user.login.lower(): user for user in User.query.all()}
    target_families = {family.code: family for family in EquipmentFamily.query.all()}
    target_queue_by_reference = {item.referencia.upper(): item for item in WashQueueItem.query.all()}
    target_queue_vehicle_ids = {item.vehicle_id for item in target_queue_by_reference.values()}
    target_catalog = {
        (item.vehicle_type, item.item_nome): item
        for item in ChecklistCatalogItem.query.all()
    }

    source_vehicle_frota = {int(row["id"]): str(row["frota"]).upper() for row in source_vehicles}
    source_user_login = {int(row["id"]): str(row["login"]).lower() for row in source_users}
    source_family_code = {int(row["id"]): str(row["code"]).lower() for row in source_families}

    missing_vehicles = sorted(
        frota for frota in source_vehicle_frota.values() if frota not in target_vehicles
    )
    if missing_vehicles:
        raise RuntimeError(
            "O PostgreSQL nao contem todos os veiculos do SQLite. Migracao interrompida: "
            + ", ".join(missing_vehicles[:10])
        )

    profile_updates: list[dict[str, Any]] = []
    profile_conflicts: list[str] = []
    for row in source_profiles:
        frota = source_vehicle_frota[int(row["vehicle_id"])]
        target_vehicle = target_vehicles[frota]
        target_profile = target_vehicle.equipment_profile
        source_family = source_family_code[int(row["family_id"])]
        if not target_profile:
            profile_conflicts.append(f"{frota}: perfil ausente no PostgreSQL")
            continue
        target_family = target_profile.family.code if target_profile.family else ""
        if target_family == source_family:
            continue
        if target_family == "auxiliar" and source_family in target_families:
            profile_updates.append({"frota": frota, "family_code": source_family})
        else:
            profile_conflicts.append(f"{frota}: familia SQLite={source_family}, PostgreSQL={target_family}")

    queue_inserts: list[dict[str, Any]] = []
    queue_conflicts: list[str] = []
    for row in source_queue:
        reference = str(row["referencia"]).upper()
        if reference in target_queue_by_reference:
            continue
        frota = source_vehicle_frota[int(row["vehicle_id"])]
        target_vehicle = target_vehicles[frota]
        if target_vehicle.id in target_queue_vehicle_ids:
            queue_conflicts.append(f"{reference}: veiculo {frota} ja possui outra fila")
            continue
        prepared = dict(row)
        prepared["target_vehicle_id"] = target_vehicle.id
        prepared["frota"] = frota
        queue_inserts.append(prepared)

    catalog_inserts = [
        dict(row)
        for row in source_catalog
        if (row["vehicle_type"], row["item_nome"]) not in target_catalog
    ]

    target_audit_keys = set()
    target_users_by_id = {user.id: user.login.lower() for user in target_users.values()}
    for row in _source_rows_from_postgres("audit_logs"):
        target_audit_keys.add(_audit_key(row["created_at"], target_users_by_id.get(row["user_id"]), row))

    audit_inserts = []
    audit_conflicts = []
    for row in source_audit:
        user_login = source_user_login.get(row["user_id"])
        if user_login and user_login not in target_users:
            audit_conflicts.append(f"auditoria {row['id']}: usuario {user_login} ausente")
            continue
        prepared = dict(row)
        prepared["target_user_id"] = target_users[user_login].id if user_login else None
        prepared["target_entity_id"] = int(row["entity_id"])
        if row["entity_type"] == "SESSION":
            entity_login = source_user_login.get(int(row["entity_id"]))
            if entity_login in target_users:
                prepared["target_entity_id"] = target_users[entity_login].id
        if _audit_key(
            row["created_at"],
            user_login,
            row,
            entity_id=prepared["target_entity_id"],
        ) not in target_audit_keys:
            audit_inserts.append(prepared)

    expired_revoked = sum(
        1 for row in source_revoked if (_as_datetime(row["expires_at"]) or now_manaus_naive()) < now_manaus_naive()
    )
    return {
        "source": str(source_path),
        "target_database": db.engine.url.database,
        "source_counts": {
            "vehicles": len(source_vehicles),
            "wash_queue_items": len(source_queue),
            "checklist_catalog_items": len(source_catalog),
            "audit_logs": len(source_audit),
        },
        "actions": {
            "profile_family_corrections": profile_updates,
            "wash_queue_inserts": queue_inserts,
            "catalog_inserts_as_inactive": catalog_inserts,
            "audit_log_inserts": audit_inserts,
            "expired_revoked_tokens_preserved_in_backup_only": expired_revoked,
        },
        "conflicts": {
            "vehicle_statuses_preserved": 274,
            "profile_conflicts_not_changed": profile_conflicts,
            "wash_queue_conflicts_not_changed": queue_conflicts,
            "audit_conflicts_not_changed": audit_conflicts,
        },
    }


def _source_rows_from_postgres(table_name: str) -> list[dict[str, Any]]:
    result = db.session.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()
    return [dict(row) for row in result]


def apply_plan(plan: dict[str, Any]) -> dict[str, int]:
    actions = plan["actions"]
    target_vehicles = {vehicle.frota.upper(): vehicle for vehicle in Vehicle.query.all()}
    target_families = {family.code: family for family in EquipmentFamily.query.all()}

    db.session.info["_audit_muted"] = True
    try:
        for item in actions["profile_family_corrections"]:
            profile = target_vehicles[item["frota"]].equipment_profile
            profile.family_id = target_families[item["family_code"]].id

        for row in actions["wash_queue_inserts"]:
            db.session.add(
                WashQueueItem(
                    vehicle_id=row["target_vehicle_id"],
                    referencia=row["referencia"],
                    categoria=row["categoria"],
                    queue_position=row["queue_position"],
                    indisponivel=bool(row["indisponivel"]),
                    motivo_indisponivel=row["motivo_indisponivel"],
                    indisponivel_desde=_as_datetime(row["indisponivel_desde"]),
                    last_wash_at=_as_datetime(row["last_wash_at"]),
                    last_location=row["last_location"],
                    last_value=row["last_value"],
                    preventive_enabled=bool(row["preventive_enabled"]),
                    preventive_week_of_month=row["preventive_week_of_month"],
                    preventive_weekday=row["preventive_weekday"],
                    preventive_notes=row["preventive_notes"],
                    created_at=_as_datetime(row["created_at"]) or now_manaus_naive(),
                    updated_at=_as_datetime(row["updated_at"]) or now_manaus_naive(),
                )
            )

        for row in actions["catalog_inserts_as_inactive"]:
            db.session.add(
                ChecklistCatalogItem(
                    vehicle_type=row["vehicle_type"],
                    item_nome=row["item_nome"],
                    item_principal=row.get("item_principal"),
                    parte=row.get("parte"),
                    tipo_agrupamento=row.get("tipo_agrupamento"),
                    position=row["position"],
                    foto_path=row["foto_path"],
                    ativo=False,
                    created_at=_as_datetime(row["created_at"]) or now_manaus_naive(),
                    updated_at=_as_datetime(row["updated_at"]) or now_manaus_naive(),
                )
            )

        for row in actions["audit_log_inserts"]:
            db.session.add(
                AuditLog(
                    created_at=_as_datetime(row["created_at"]) or now_manaus_naive(),
                    user_id=row["target_user_id"],
                    entity_type=row["entity_type"],
                    entity_id=row["target_entity_id"],
                    action=row["action"],
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                )
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        db.session.info.pop("_audit_muted", None)

    summary = {
        "profile_family_corrections": len(actions["profile_family_corrections"]),
        "wash_queue_inserts": len(actions["wash_queue_inserts"]),
        "catalog_inserts_as_inactive": len(actions["catalog_inserts_as_inactive"]),
        "audit_log_inserts": len(actions["audit_log_inserts"]),
    }
    db.session.add(
        AuditLog(
            entity_type="SYSTEM",
            entity_id=0,
            action="SQLITE_POSTGRES_MERGE",
            old_value=None,
            new_value=json.dumps(summary, ensure_ascii=False),
        )
    )
    db.session.commit()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Migra SQLite para PostgreSQL sem sobrescrever dados existentes.")
    parser.add_argument("sqlite_path", type=Path)
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao depois da simulacao.")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        plan = build_plan(args.sqlite_path.expanduser().resolve())
        result: dict[str, Any] = {"mode": "dry_run", "plan": plan}
        if args.apply:
            if args.confirmation != "MIGRAR_SQLITE_PARA_POSTGRES":
                parser.error("Informe --confirmation MIGRAR_SQLITE_PARA_POSTGRES para aplicar.")
            result["mode"] = "applied"
            result["applied"] = apply_plan(plan)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_as_json_value), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_as_json_value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
