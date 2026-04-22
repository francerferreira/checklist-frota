from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db
from app.models.activity import ActivityNonConformityLink


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

    ActivityNonConformityLink.__table__.create(bind=db.engine, checkfirst=True)
