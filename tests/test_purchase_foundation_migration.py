from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260816_0017_purchases_foundation.py"


class PurchaseFoundationMigrationTests(unittest.TestCase):
    def test_upgrade_is_idempotent_and_preserves_legacy_tables(self):
        path = Path(tempfile.gettempdir()) / "checklist_frota_purchase_foundation_migration_test.db"
        if path.exists():
            path.unlink()
        engine = sa.create_engine(f"sqlite:///{path}")
        metadata = sa.MetaData()
        sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("vehicles", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("materials", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("maintenance_materials", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("suppliers", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("code", sa.String(40)), sa.Column("name", sa.String(180)))
        sa.Table(
            "purchase_requests", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("material_id", sa.Integer, nullable=False),
            sa.Column("requested_quantity", sa.Integer, nullable=False),
            sa.Column("received_quantity", sa.Integer, nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("priority", sa.String(20), nullable=False),
            sa.Column("created_by_user_id", sa.Integer, nullable=False),
        )
        metadata.create_all(engine)
        spec = importlib.util.spec_from_file_location("purchase_foundation_migration", MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            tables = set(sa.inspect(connection).get_table_names())
            expected = {"purchase_import_batches", "purchase_import_source_rows", "purchase_service_catalog", "purchase_request_items", "purchase_orders", "purchase_order_items", "purchase_invoices", "invoice_purchase_order_links", "purchase_invoice_items", "purchase_process_events"}
            self.assertTrue(expected.issubset(tables))
            self.assertIn("sc_number", {column["name"] for column in sa.inspect(connection).get_columns("purchase_requests")})
            self.assertTrue({"users", "materials", "suppliers", "purchase_requests"}.issubset(tables))
            migration.downgrade()
            self.assertTrue({"users", "materials", "suppliers", "purchase_requests"}.issubset(set(sa.inspect(connection).get_table_names())))
        engine.dispose()
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    unittest.main()
