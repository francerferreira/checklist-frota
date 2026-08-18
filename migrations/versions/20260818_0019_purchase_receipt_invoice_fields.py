"""Add structured invoice fields to purchase receipts."""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0019"
down_revision = "20260817_0018"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table, column):
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def upgrade():
    for column in (
        sa.Column("invoice_number", sa.String(80), nullable=True),
        sa.Column("invoice_series", sa.String(30), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("invoice_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("invoice_file_path", sa.String(500), nullable=True),
    ):
        _add_column("purchase_receipts", column)

    if "purchase_receipts" in _tables():
        indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("purchase_receipts")}
        if "ix_purchase_receipts_invoice_number" not in indexes:
            op.create_index("ix_purchase_receipts_invoice_number", "purchase_receipts", ["invoice_number"])


def downgrade():
    if "purchase_receipts" not in _tables():
        return
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("purchase_receipts")}
    if "ix_purchase_receipts_invoice_number" in indexes:
        op.drop_index("ix_purchase_receipts_invoice_number", table_name="purchase_receipts")
    columns = _columns("purchase_receipts")
    existing = [name for name in ("invoice_file_path", "invoice_value", "invoice_date", "invoice_series", "invoice_number") if name in columns]
    if existing:
        with op.batch_alter_table("purchase_receipts", recreate="always") as batch:
            for name in existing:
                batch.drop_column(name)
