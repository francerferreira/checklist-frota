from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = PROJECT_ROOT / "migrations" / "versions" / "20260712_0002_availability_hourmeter_phase_2.py"


class Phase2MigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_downgrade_preserves_legacy_data(self):
        database_path = Path(tempfile.gettempdir()) / "checklist_frota_phase2_migration_test.db"
        if database_path.exists():
            database_path.unlink()
        engine = sa.create_engine(f"sqlite:///{database_path}")
        metadata = sa.MetaData()
        users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        vehicles = sa.Table("vehicles", metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)

        spec = importlib.util.spec_from_file_location("phase2_migration", MIGRATION_PATH)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            connection.execute(users.insert(), [{"id": 1}])
            connection.execute(vehicles.insert(), [{"id": 10}, {"id": 20}])
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()

            inspector = sa.inspect(connection)
            self.assertTrue({
                "equipment_operational_states", "equipment_status_events", "hourmeter_readings"
            }.issubset(inspector.get_table_names()))
            state_count = connection.execute(
                sa.text("SELECT COUNT(*) FROM equipment_operational_states")
            ).scalar_one()
            self.assertEqual(state_count, 2)
            statuses = connection.execute(
                sa.text("SELECT DISTINCT operational_status FROM equipment_operational_states")
            ).scalars().all()
            self.assertEqual(statuses, ["SEM_APONTAMENTO"])

            migration.downgrade()
            remaining_tables = set(sa.inspect(connection).get_table_names())
            self.assertNotIn("equipment_operational_states", remaining_tables)
            self.assertNotIn("equipment_status_events", remaining_tables)
            self.assertNotIn("hourmeter_readings", remaining_tables)
            self.assertEqual(connection.execute(sa.text("SELECT COUNT(*) FROM vehicles")).scalar_one(), 2)

        engine.dispose()
        if database_path.exists():
            database_path.unlink()


if __name__ == "__main__":
    unittest.main()
