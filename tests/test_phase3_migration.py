from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260712_0003_technical_inspections_phase_3.py"


class Phase3MigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_rollback_preserves_parent_tables(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_phase3_migration_test.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        for name in ("users", "vehicles", "equipment_families", "mechanic_non_conformities"):
            sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)
        spec = importlib.util.spec_from_file_location("phase3_migration", MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            tables = set(sa.inspect(connection).get_table_names())
            self.assertTrue({
                "inspection_templates", "inspection_template_items",
                "inspection_executions", "inspection_execution_items",
            }.issubset(tables))
            migration.downgrade()
            tables = set(sa.inspect(connection).get_table_names())
            self.assertTrue({"users", "vehicles", "equipment_families"}.issubset(tables))
            self.assertNotIn("inspection_templates", tables)
        engine.dispose()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    unittest.main()
