from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260717_0010_equipment_location_movements_phase_3a.py"
)


class Phase3ALocationMigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_downgrade_preserves_core_tables(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_phase3a_location_migration_test.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("vehicles", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("operational_locations", metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)

        spec = importlib.util.spec_from_file_location("phase3a_location_migration", MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            inspector = sa.inspect(connection)
            self.assertIn("equipment_location_movements", set(inspector.get_table_names()))
            self.assertEqual(
                {
                    "id",
                    "vehicle_id",
                    "from_location_id",
                    "to_location_id",
                    "reason",
                    "notes",
                    "source",
                    "moved_at",
                    "created_by_user_id",
                    "created_at",
                },
                {column["name"] for column in inspector.get_columns("equipment_location_movements")},
            )
            self.assertTrue(
                {
                    "ix_equipment_location_movements_vehicle_id",
                    "ix_equipment_location_movements_moved_at",
                    "ix_equipment_location_movements_to_location_id",
                }.issubset(
                    {index["name"] for index in inspector.get_indexes("equipment_location_movements")}
                )
            )
            self.assertEqual(
                {"vehicles", "operational_locations", "users"},
                {
                    foreign_key["referred_table"]
                    for foreign_key in inspector.get_foreign_keys("equipment_location_movements")
                },
            )
            self.assertEqual(
                {
                    "ck_equipment_location_movement_distinct",
                    "ck_equipment_location_movement_source",
                },
                {
                    constraint["name"]
                    for constraint in inspector.get_check_constraints(
                        "equipment_location_movements"
                    )
                },
            )
            migration.downgrade()
            tables = set(sa.inspect(connection).get_table_names())
            self.assertNotIn("equipment_location_movements", tables)
            self.assertTrue({"users", "vehicles", "operational_locations"}.issubset(tables))

        engine.dispose()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    unittest.main()
