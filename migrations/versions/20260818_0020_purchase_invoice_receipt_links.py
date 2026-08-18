"""Link canonical invoices and receipts to purchase order items."""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0020"
down_revision = "20260818_0019"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table, column):
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def _add_index(name, table, columns):
    if table not in _tables():
        return
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns)


def upgrade():
    _add_column("purchase_invoices", sa.Column("file_path", sa.String(500), nullable=True))
    _add_column("purchase_receipts", sa.Column("purchase_invoice_id", sa.Integer(), sa.ForeignKey("purchase_invoices.id"), nullable=True))
    _add_column("purchase_receipts", sa.Column("purchase_order_item_id", sa.Integer(), sa.ForeignKey("purchase_order_items.id"), nullable=True))
    _add_index("ix_purchase_receipts_purchase_invoice_id", "purchase_receipts", ["purchase_invoice_id"])
    _add_index("ix_purchase_receipts_purchase_order_item_id", "purchase_receipts", ["purchase_order_item_id"])


def downgrade():
    if "purchase_receipts" in _tables():
        indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("purchase_receipts")}
        for name in ("ix_purchase_receipts_purchase_order_item_id", "ix_purchase_receipts_purchase_invoice_id"):
            if name in indexes:
                op.drop_index(name, table_name="purchase_receipts")
        columns = _columns("purchase_receipts")
        existing = [name for name in ("purchase_order_item_id", "purchase_invoice_id") if name in columns]
        if existing:
            with op.batch_alter_table("purchase_receipts", recreate="always") as batch:
                for name in existing:
                    batch.drop_column(name)
    if "purchase_invoices" in _tables() and "file_path" in _columns("purchase_invoices"):
        with op.batch_alter_table("purchase_invoices", recreate="always") as batch:
            batch.drop_column("file_path")
