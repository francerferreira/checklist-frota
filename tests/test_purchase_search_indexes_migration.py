from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260820_0023_purchase_search_indexes.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("purchase_search_indexes", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_purchase_search_indexes_are_idempotent_and_reversible(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'purchase-search-indexes.db'}")
    metadata = sa.MetaData()
    sa.Table(
        "purchase_requests",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("status", sa.String(30)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("sc_number", sa.String(60)),
    )
    sa.Table(
        "purchase_request_items",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_request_id", sa.Integer),
        sa.Column("status", sa.String(30)),
        sa.Column("description_raw", sa.Text),
        sa.Column("manual_reference_raw", sa.String(180)),
    )
    sa.Table(
        "purchase_orders",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("pc_number", sa.String(60)),
        sa.Column("status", sa.String(30)),
        sa.Column("created_at", sa.DateTime),
    )
    sa.Table(
        "purchase_invoices",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_number", sa.String(80)),
        sa.Column("status", sa.String(30)),
        sa.Column("invoice_date", sa.Date),
    )
    sa.Table(
        "materials",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("codigo_produto", sa.String(120)),
        sa.Column("referencia", sa.String(80)),
        sa.Column("descricao", sa.String(255)),
    )
    metadata.create_all(engine)
    migration = load_migration()
    expected = {name for _table, name, _columns in migration.INDEXES}

    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        indexes = {
            index["name"]
            for table in {table for table, _name, _columns in migration.INDEXES}
            for index in sa.inspect(connection).get_indexes(table)
        }
        assert expected.issubset(indexes)
        migration.downgrade()
        indexes_after_downgrade = {
            index["name"]
            for table in {table for table, _name, _columns in migration.INDEXES}
            for index in sa.inspect(connection).get_indexes(table)
        }
        assert not expected.intersection(indexes_after_downgrade)

    engine.dispose()
