from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_official_environment_requires_explicit_database_and_sqlite_opt_in():
    source = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")

    assert "DATABASE_URL e obrigatoria" in source
    assert "CHECKLIST_ALLOW_SQLITE=1" in source
    assert "CHECKLIST_LEGACY_LOCAL_BOOTSTRAP" in source


def test_startup_schema_is_restricted_to_the_legacy_sqlite_test_profile():
    source = (ROOT / "backend" / "app" / "__init__.py").read_text(encoding="utf-8")
    runtime_schema = (ROOT / "backend" / "app" / "services" / "runtime_schema_service.py").read_text(
        encoding="utf-8"
    )

    assert 'if app.config["LEGACY_LOCAL_BOOTSTRAP_ENABLED"]:' in source
    assert "Alteracao automatica de schema esta desativada" in runtime_schema
    assert 'db.engine.dialect.name != "sqlite"' in runtime_schema
