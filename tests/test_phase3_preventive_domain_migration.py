from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260726_0015_preventive_domain_phase_3.py"


class PreventiveDomainMigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_downgrade_preserves_existing_tables(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_preventive_domain_migration_test.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        for name in ("users", "vehicles", "preventive_plans", "maintenance_work_orders", "materials"):
            sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table(
            "hourmeter_readings",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("vehicle_id", sa.Integer),
            sa.Column("reading", sa.Numeric(12, 2)),
            sa.Column("recorded_at", sa.DateTime),
        )
        sa.Table(
            "audit_logs",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer, nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
        )
        metadata.create_all(engine)

        spec = importlib.util.spec_from_file_location("preventive_domain_migration", MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()

            tables = set(sa.inspect(connection).get_table_names())
            self.assertTrue({"preventive_executions", "preventive_stages", "preventive_materials"}.issubset(tables))
            hourmeter_columns = {column["name"] for column in sa.inspect(connection).get_columns("hourmeter_readings")}
            self.assertTrue({"previous_reading", "difference_hours", "validation_status", "cancelled_at"}.issubset(hourmeter_columns))

            connection.execute(
                sa.text(
                    "INSERT INTO preventive_executions "
                    "(vehicle_id, preventive_plan_id, status, created_at, updated_at) "
                    "VALUES (1, 1, 'PLANEJADA', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            migration.downgrade()
            tables = set(sa.inspect(connection).get_table_names())
            self.assertNotIn("preventive_executions", tables)
            self.assertNotIn("preventive_stages", tables)
            self.assertNotIn("preventive_materials", tables)
            self.assertTrue({"users", "vehicles", "preventive_plans", "materials"}.issubset(tables))

        engine.dispose()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    unittest.main()
