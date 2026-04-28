from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db
from app.models.activity import ActivityNonConformityLink


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
    db.session.execute(text("DROP TABLE IF EXISTS checklist_catalog_items_new"))
    db.session.execute(
        text(
            f"""
            CREATE TABLE checklist_catalog_items_new (
                id INTEGER PRIMARY KEY,
                vehicle_type VARCHAR(20) NOT NULL,
                item_nome VARCHAR(160) NOT NULL,
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
            """
            INSERT INTO checklist_catalog_items_new
            (id, vehicle_type, item_nome, position, foto_path, ativo, created_at, updated_at)
            SELECT id, vehicle_type, item_nome, position, foto_path, ativo, created_at, updated_at
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


def ensure_runtime_schema() -> None:
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
        if "resolved_by_user_id" not in columns:
            db.session.execute(text("ALTER TABLE checklist_items ADD COLUMN resolved_by_user_id INTEGER"))
            db.session.commit()

    if "activities" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("activities")}
        if "assigned_mechanic_user_id" not in columns:
            db.session.execute(text("ALTER TABLE activities ADD COLUMN assigned_mechanic_user_id INTEGER"))
            db.session.commit()
        if "source_type" not in columns:
            db.session.execute(text("ALTER TABLE activities ADD COLUMN source_type VARCHAR(40)"))
            db.session.commit()
        if "source_key" not in columns:
            db.session.execute(text("ALTER TABLE activities ADD COLUMN source_key VARCHAR(180)"))
            db.session.commit()
        if "source_modulo" not in columns:
            db.session.execute(text("ALTER TABLE activities ADD COLUMN source_modulo VARCHAR(20)"))
            db.session.commit()
        if "auto_link_nc" not in columns:
            db.session.execute(text("ALTER TABLE activities ADD COLUMN auto_link_nc BOOLEAN DEFAULT FALSE"))
            db.session.commit()

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
