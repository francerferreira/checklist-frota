from __future__ import annotations

from sqlalchemy import inspect, text
from flask import current_app

from app.extensions import db
from app.models.activity import ActivityNonConformityLink
from app.models.dashboard_tv_access import DashboardTvAccessToken
from app.models.resolution_package import ResolutionPackage, ResolutionPackageLink
from app.models.maintenance import MaintenanceWorkOrder, MaintenanceWorkOrderCost
from app.models.system_setting import SystemSetting
from app.services.checklist_catalog import classify_catalog_item_group


_CHECKLIST_CATALOG_ALLOWED_TYPES = (
    "cavalo",
    "carreta",
    "carro_simples",
    "cavalo_auxiliar",
    "ambulancia",
    "caminhao_pipa",
    "caminhao_brigada",
    "onibus",
    "van",
)


def _check_sql_includes_all_types(sql_text: str | None) -> bool:
    normalized = (sql_text or "").lower()
    return all(f"'{item}'" in normalized for item in _CHECKLIST_CATALOG_ALLOWED_TYPES)


def _ensure_checklist_catalog_constraint_postgres() -> None:
    expected = ", ".join(f"'{item}'" for item in _CHECKLIST_CATALOG_ALLOWED_TYPES)
    db.session.execute(
        text(
            f"""
            ALTER TABLE checklist_catalog_items
            DROP CONSTRAINT IF EXISTS ck_checklist_catalog_vehicle_type
            """
        )
    )
    db.session.execute(
        text(
            f"""
            ALTER TABLE checklist_catalog_items
            ADD CONSTRAINT ck_checklist_catalog_vehicle_type
            CHECK (vehicle_type IN ({expected}))
            """
        )
    )
    db.session.commit()


def _ensure_checklist_catalog_constraint_sqlite() -> None:
    expected = ", ".join(f"'{item}'" for item in _CHECKLIST_CATALOG_ALLOWED_TYPES)
    existing_columns = {
        column["name"] for column in inspect(db.engine).get_columns("checklist_catalog_items")
    }
    item_principal_select = "item_principal" if "item_principal" in existing_columns else "NULL"
    parte_select = "parte" if "parte" in existing_columns else "NULL"
    tipo_agrupamento_select = "tipo_agrupamento" if "tipo_agrupamento" in existing_columns else "NULL"
    db.session.execute(text("DROP TABLE IF EXISTS checklist_catalog_items_new"))
    db.session.execute(
        text(
            f"""
            CREATE TABLE checklist_catalog_items_new (
                id INTEGER PRIMARY KEY,
                vehicle_type VARCHAR(20) NOT NULL,
                item_nome VARCHAR(160) NOT NULL,
                item_principal VARCHAR(160),
                parte VARCHAR(80),
                tipo_agrupamento VARCHAR(40),
                position INTEGER NOT NULL DEFAULT 1,
                foto_path VARCHAR(255),
                ativo BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_checklist_catalog_type_name UNIQUE (vehicle_type, item_nome),
                CONSTRAINT ck_checklist_catalog_vehicle_type CHECK (vehicle_type IN ({expected})),
                CONSTRAINT ck_checklist_catalog_position_positive CHECK (position > 0)
            )
            """
        )
    )
    db.session.execute(
        text(
            f"""
            INSERT INTO checklist_catalog_items_new
            (id, vehicle_type, item_nome, item_principal, parte, tipo_agrupamento, position, foto_path, ativo, created_at, updated_at)
            SELECT id, vehicle_type, item_nome, {item_principal_select}, {parte_select}, {tipo_agrupamento_select}, position, foto_path, ativo, created_at, updated_at
            FROM checklist_catalog_items
            """
        )
    )
    db.session.execute(text("DROP TABLE checklist_catalog_items"))
    db.session.execute(text("ALTER TABLE checklist_catalog_items_new RENAME TO checklist_catalog_items"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_checklist_catalog_items_vehicle_type ON checklist_catalog_items (vehicle_type)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_checklist_catalog_items_item_nome ON checklist_catalog_items (item_nome)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_checklist_catalog_items_position ON checklist_catalog_items (position)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_checklist_catalog_items_ativo ON checklist_catalog_items (ativo)"))
    db.session.commit()


def _ensure_checklist_catalog_constraint(inspector) -> None:
    if "checklist_catalog_items" not in inspector.get_table_names():
        return

    constraints = inspector.get_check_constraints("checklist_catalog_items")
    target = next((item for item in constraints if item.get("name") == "ck_checklist_catalog_vehicle_type"), None)
    sql_text = (target or {}).get("sqltext") if target else " ".join((item.get("sqltext") or "") for item in constraints)
    if _check_sql_includes_all_types(sql_text):
        return

    dialect = db.engine.dialect.name.lower()
    if dialect == "sqlite":
        _ensure_checklist_catalog_constraint_sqlite()
    else:
        _ensure_checklist_catalog_constraint_postgres()


def _ensure_column(table_name: str, columns: set[str], column_name: str, column_sql: str) -> None:
    if column_name not in columns:
        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))
        db.session.commit()
        columns.add(column_name)


def _backfill_checklist_item_grouping() -> None:
    rows = db.session.execute(
        text(
            """
            SELECT checklist_items.id, checklist_items.item_nome, vehicles.tipo AS vehicle_type
            FROM checklist_items
            JOIN checklists ON checklists.id = checklist_items.checklist_id
            JOIN vehicles ON vehicles.id = checklists.vehicle_id
            WHERE checklist_items.item_principal IS NULL
               OR checklist_items.tipo_agrupamento IS NULL
               OR checklist_items.item_origem IS NULL
            """
        )
    ).mappings().all()
    if not rows:
        return

    for row in rows:
        try:
            grouping = classify_catalog_item_group(row["vehicle_type"], row["item_nome"])
        except ValueError:
            grouping = {
                "item_principal": (row["item_nome"] or "").strip().upper(),
                "parte": None,
                "tipo_agrupamento": "simples",
                "item_origem": (row["item_nome"] or "").strip().upper(),
            }
        db.session.execute(
            text(
                """
                UPDATE checklist_items
                SET item_principal = :item_principal,
                    parte = :parte,
                    tipo_agrupamento = :tipo_agrupamento,
                    item_origem = :item_origem
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "item_principal": grouping["item_principal"],
                "parte": grouping.get("parte"),
                "tipo_agrupamento": grouping["tipo_agrupamento"],
                "item_origem": grouping["item_origem"],
            },
        )
    db.session.commit()


def ensure_runtime_schema() -> None:
    if not current_app.config.get("LEGACY_LOCAL_BOOTSTRAP_ENABLED"):
        raise RuntimeError(
            "Alteracao automatica de schema esta desativada. Use Alembic para PostgreSQL."
        )
    if db.engine.dialect.name != "sqlite":
        raise RuntimeError(
            "Alteracao automatica de schema e restrita ao SQLite temporario de testes."
        )
    inspector = inspect(db.engine)

    if "wash_records" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("wash_records")}
        if "turno" not in columns:
            db.session.execute(text("ALTER TABLE wash_records ADD COLUMN turno VARCHAR(20)"))
            db.session.commit()
        if "foto_path" not in columns:
            db.session.execute(text("ALTER TABLE wash_records ADD COLUMN foto_path VARCHAR(255)"))
            db.session.commit()

    if "checklist_items" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("checklist_items")}
        _ensure_column("checklist_items", columns, "item_principal", "VARCHAR(160)")
        _ensure_column("checklist_items", columns, "parte", "VARCHAR(80)")
        _ensure_column("checklist_items", columns, "tipo_agrupamento", "VARCHAR(40)")
        _ensure_column("checklist_items", columns, "item_origem", "VARCHAR(160)")
        if "resolved_by_user_id" not in columns:
            db.session.execute(text("ALTER TABLE checklist_items ADD COLUMN resolved_by_user_id INTEGER"))
            db.session.commit()
        _backfill_checklist_item_grouping()

    if "checklist_catalog_items" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("checklist_catalog_items")}
        _ensure_column("checklist_catalog_items", columns, "item_principal", "VARCHAR(160)")
        _ensure_column("checklist_catalog_items", columns, "parte", "VARCHAR(80)")
        _ensure_column("checklist_catalog_items", columns, "tipo_agrupamento", "VARCHAR(40)")

    if "activities" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("activities")}
        _ensure_column("activities", columns, "assigned_mechanic_user_id", "INTEGER")
        _ensure_column("activities", columns, "source_type", "VARCHAR(40)")
        _ensure_column("activities", columns, "source_key", "VARCHAR(180)")
        _ensure_column("activities", columns, "source_modulo", "VARCHAR(20)")
        _ensure_column("activities", columns, "auto_link_nc", "BOOLEAN DEFAULT FALSE")

    if "maintenance_work_orders" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("maintenance_work_orders")}
        _ensure_column("maintenance_work_orders", columns, "failure_cause", "VARCHAR(160)")
        _ensure_column("maintenance_work_orders", columns, "affected_component", "VARCHAR(160)")
        _ensure_column("maintenance_work_orders", columns, "work_shift", "VARCHAR(30)")

    if "activity_items" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("activity_items")}
        if "material_id" not in columns:
            db.session.execute(text("ALTER TABLE activity_items ADD COLUMN material_id INTEGER"))
            db.session.commit()
        if "quantidade_peca" not in columns:
            db.session.execute(text("ALTER TABLE activity_items ADD COLUMN quantidade_peca INTEGER DEFAULT 1"))
            db.session.commit()
        if "codigo_peca" not in columns:
            db.session.execute(text("ALTER TABLE activity_items ADD COLUMN codigo_peca VARCHAR(80)"))
            db.session.commit()
        if "descricao_peca" not in columns:
            db.session.execute(text("ALTER TABLE activity_items ADD COLUMN descricao_peca VARCHAR(255)"))
            db.session.commit()

    _ensure_checklist_catalog_constraint(inspector)

    ActivityNonConformityLink.__table__.create(bind=db.engine, checkfirst=True)
    DashboardTvAccessToken.__table__.create(bind=db.engine, checkfirst=True)
    ResolutionPackage.__table__.create(bind=db.engine, checkfirst=True)
    ResolutionPackageLink.__table__.create(bind=db.engine, checkfirst=True)
    MaintenanceWorkOrder.__table__.create(bind=db.engine, checkfirst=True)
    MaintenanceWorkOrderCost.__table__.create(bind=db.engine, checkfirst=True)
    SystemSetting.__table__.create(bind=db.engine, checkfirst=True)
