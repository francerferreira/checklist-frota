from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260712_0005_pcm_preventive_plans_phase_5.py"


class Phase5MigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_rollback_preserves_parents(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_phase5_migration_test.db"
        if path.exists(): path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        for name in ("users", "vehicles"):
            sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)
        spec = importlib.util.spec_from_file_location("phase5_migration", MIGRATION)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection)); migration.upgrade(); migration.upgrade()
            self.assertIn("preventive_plans", set(sa.inspect(connection).get_table_names()))
            migration.downgrade(); self.assertNotIn("preventive_plans", set(sa.inspect(connection).get_table_names()))
        engine.dispose()
        if path.exists(): path.unlink()


if __name__ == "__main__":
    unittest.main()
