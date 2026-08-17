from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260816_0016_mmp_warehouse.py"


class MmpWarehouseMigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_downgrade_preserves_existing_tables(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_mmp_migration_test.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        for name in ("users", "vehicles", "materials", "warehouses", "warehouse_stocks", "material_movements"):
            sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
        metadata.create_all(engine)
        spec = importlib.util.spec_from_file_location("mmp_warehouse_migration", MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            tables = set(sa.inspect(connection).get_table_names())
            self.assertTrue({"warehouse_locations", "warehouse_transfers", "warehouse_transfer_items"}.issubset(tables))
            self.assertIn("warehouse_type", {column["name"] for column in sa.inspect(connection).get_columns("warehouses")})
            migration.downgrade()
            self.assertTrue({"users", "materials", "warehouses"}.issubset(set(sa.inspect(connection).get_table_names())))
        engine.dispose()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    unittest.main()
