from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db


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
