"""Add database-native full-text search for purchase descriptions."""

from alembic import op
import sqlalchemy as sa
import re


revision = "20260820_0024"
down_revision = "20260820_0023"
branch_labels = None
depends_on = None


SQLITE_SOURCES = {
    "MATERIAL": ("materials", "coalesce(referencia, '') || ' ' || coalesce(descricao, '') || ' ' || coalesce(codigo_produto, '') || ' ' || coalesce(marca, '') || ' ' || coalesce(referencia_manual, '') || ' ' || coalesce(numero_fabricante, '')"),
    "REQUEST": ("purchase_requests", "coalesce(code, '') || ' ' || coalesce(sc_number, '') || ' ' || coalesce(module, '') || ' ' || coalesce(requester_raw, '') || ' ' || coalesce(equipment_raw, '') || ' ' || coalesce(cost_center, '') || ' ' || coalesce(justification, '')"),
    "REQUEST_ITEM": ("purchase_request_items", "coalesce(product_code_raw, '') || ' ' || coalesce(description_raw, '') || ' ' || coalesce(manual_reference_raw, '') || ' ' || coalesce(brand_raw, '') || ' ' || coalesce(manufacturer_part_number_raw, '')"),
    "SERVICE": ("purchase_service_catalog", "coalesce(code, '') || ' ' || coalesce(service_name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(specialty, '')"),
    "SUPPLIER": ("suppliers", "coalesce(code, '') || ' ' || coalesce(name, '') || ' ' || coalesce(legal_name, '') || ' ' || coalesce(trade_name, '')"),
    "PC": ("purchase_orders", "coalesce(pc_number, '') || ' ' || coalesce(supplier_raw, '') || ' ' || coalesce(notes, '')"),
    "NF": ("purchase_invoices", "coalesce(invoice_number, '') || ' ' || coalesce(series, '') || ' ' || coalesce(access_key, '') || ' ' || coalesce(supplier_raw, '') || ' ' || coalesce(notes, '')"),
}


POSTGRES_INDEXES = (
    ("ix_materials_fulltext_search", "materials", "descricao"),
    ("ix_purchase_request_items_fulltext_search", "purchase_request_items", "description_raw"),
    ("ix_purchase_services_fulltext_search", "purchase_service_catalog", "service_name"),
)


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _sqlite_insert(entity_type, table, expression, alias="NEW"):
    qualified_expression = re.sub(r"\bcoalesce\(([A-Za-z_][A-Za-z0-9_]*)", rf"coalesce({alias}.\1", expression)
    return (
        "INSERT INTO purchase_search_fts(entity_type, entity_id, content) "
        f"VALUES ('{entity_type}', {alias}.id, trim({qualified_expression}));"
    )


def _create_sqlite_trigger(entity_type, table, expression):
    trigger_prefix = f"purchase_search_fts_{table}"
    op.execute(
        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_ai AFTER INSERT ON {table} BEGIN "
        f"{_sqlite_insert(entity_type, table, expression)} END;"
    )
    op.execute(
        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_au AFTER UPDATE ON {table} BEGIN "
        f"DELETE FROM purchase_search_fts WHERE entity_type = '{entity_type}' AND entity_id = OLD.id; "
        f"{_sqlite_insert(entity_type, table, expression)} END;"
    )
    op.execute(
        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_ad AFTER DELETE ON {table} BEGIN "
        f"DELETE FROM purchase_search_fts WHERE entity_type = '{entity_type}' AND entity_id = OLD.id; END;"
    )


def _upgrade_sqlite():
    tables = _table_names()
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS purchase_search_fts USING fts5("
        "entity_type UNINDEXED, entity_id UNINDEXED, content, "
        "tokenize='unicode61 remove_diacritics 2')"
    )
    op.execute("DELETE FROM purchase_search_fts")
    for entity_type, (table, expression) in SQLITE_SOURCES.items():
        if table not in tables:
            continue
        op.execute(
            "INSERT INTO purchase_search_fts(entity_type, entity_id, content) "
            f"SELECT '{entity_type}', id, trim({expression}) FROM {table}"
        )
        _create_sqlite_trigger(entity_type, table, expression)


def _upgrade_postgresql():
    for name, table, column in POSTGRES_INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {table} "
            f"USING gin (to_tsvector('simple', coalesce({column}, '')))"
        )


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        _upgrade_sqlite()
    elif op.get_bind().dialect.name.startswith("postgresql"):
        _upgrade_postgresql()


def _downgrade_sqlite():
    for entity_type, (table, _expression) in SQLITE_SOURCES.items():
        op.execute(f"DROP TRIGGER IF EXISTS purchase_search_fts_{table}_ad")
        op.execute(f"DROP TRIGGER IF EXISTS purchase_search_fts_{table}_au")
        op.execute(f"DROP TRIGGER IF EXISTS purchase_search_fts_{table}_ai")
    op.execute("DROP TABLE IF EXISTS purchase_search_fts")


def _downgrade_postgresql():
    for name, _table, _column in POSTGRES_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        _downgrade_sqlite()
    elif op.get_bind().dialect.name.startswith("postgresql"):
        _downgrade_postgresql()
