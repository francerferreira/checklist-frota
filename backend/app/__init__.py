from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask
from dotenv import load_dotenv

from app.extensions import cors, db, migrate
from app.routes import register_blueprints
from app.services.audit_service import install_audit_hooks
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
    cors.init_app(app, resources={r"/*": {"origins": "*"}})

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_runtime_schema()
        db.create_all()
        seed_reference_data()
        install_audit_hooks()

    return app
