"""Add indexes used by the Web purchase searches."""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0023"
down_revision = "20260820_0022"
branch_labels = None
depends_on = None


INDEXES = (
    ("purchase_requests", "ix_purchase_requests_status_created_at", ("status", "created_at")),
    ("purchase_requests", "ix_purchase_requests_sc_number_created_at", ("sc_number", "created_at")),
    ("purchase_request_items", "ix_purchase_request_items_description_raw", ("description_raw",)),
    ("purchase_request_items", "ix_purchase_request_items_manual_reference_raw", ("manual_reference_raw",)),
    ("purchase_request_items", "ix_purchase_request_items_status_request_id", ("status", "purchase_request_id")),
    ("purchase_orders", "ix_purchase_orders_pc_number_created_at", ("pc_number", "created_at")),
    ("purchase_orders", "ix_purchase_orders_status_created_at", ("status", "created_at")),
    ("purchase_invoices", "ix_purchase_invoices_number_date", ("invoice_number", "invoice_date")),
    ("purchase_invoices", "ix_purchase_invoices_status_date", ("status", "invoice_date")),
    ("materials", "ix_materials_search_codigo_descricao", ("codigo_produto", "descricao")),
    ("materials", "ix_materials_search_referencia_descricao", ("referencia", "descricao")),
)


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table):
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def _column_names(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    tables = _table_names()
    for table, name, columns in INDEXES:
        if table not in tables or name in _index_names(table):
            continue
        if not set(columns).issubset(_column_names(table)):
            continue
        op.create_index(name, table, list(columns))


def downgrade():
    tables = _table_names()
    for table, name, _columns in reversed(INDEXES):
        if table in tables and name in _index_names(table):
            op.drop_index(name, table_name=table)
