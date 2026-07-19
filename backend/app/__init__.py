from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask
from sqlalchemy import text
from dotenv import load_dotenv

from app.extensions import cors, db, migrate
from app.routes import register_blueprints
from app.services.audit_service import audit_runtime_status, install_audit_hooks
from app.services.runtime_schema_service import ensure_runtime_schema
from app.services.seed_service import seed_reference_data


def create_app() -> Flask:
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).resolve().parent
        parent_root = project_root.parent
    else:
        project_root = Path(__file__).resolve().parents[2]
        parent_root = None

    load_dotenv(project_root / ".env")
    if parent_root is not None:
        load_dotenv(parent_root / ".env")
    from app.config import Config

    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    allowed_origins = app.config["CORS_ALLOWED_ORIGINS"]
    # Never reflect arbitrary origins; an old environment flag must not reopen CORS.
    cors_origins = allowed_origins
    cors.init_app(app, resources={r"/*": {"origins": cors_origins}})

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            return {"status": "unavailable", "database": "unavailable", "audit": audit_runtime_status()}, 503
        audit = audit_runtime_status()
        return {"status": "ok" if audit["healthy"] else "degraded", "database": "ok", "audit": audit}, 200

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_runtime_schema()
        db.create_all()
        seed_reference_data()
        install_audit_hooks()

    return app
