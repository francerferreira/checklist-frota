from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260818_0019_purchase_receipt_invoice_fields.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("purchase_receipt_invoice_fields", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_purchase_receipt_invoice_fields_migration_is_idempotent_and_reversible(tmp_path):
    database = tmp_path / "purchase-receipt-invoice.db"
    engine = sa.create_engine(f"sqlite:///{database}")
    metadata = sa.MetaData()
    sa.Table(
        "purchase_receipts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_request_id", sa.Integer, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
    )
    metadata.create_all(engine)
    migration = load_migration()

    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("purchase_receipts")}
        assert {"invoice_number", "invoice_series", "invoice_date", "invoice_value", "invoice_file_path"}.issubset(columns)
        assert "ix_purchase_receipts_invoice_number" in {index["name"] for index in sa.inspect(connection).get_indexes("purchase_receipts")}
        migration.downgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("purchase_receipts")}
        assert not {"invoice_number", "invoice_series", "invoice_date", "invoice_value", "invoice_file_path"}.intersection(columns)
