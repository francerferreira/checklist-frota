from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260820_0024_purchase_full_text_search.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("purchase_full_text_search", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_sqlite_full_text_search_is_populated_and_reversible(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'purchase-full-text-search.db'}")
    metadata = sa.MetaData()
    sa.Table(
        "materials",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("referencia", sa.String(80)),
        sa.Column("descricao", sa.String(255)),
        sa.Column("codigo_produto", sa.String(120)),
        sa.Column("marca", sa.String(180)),
        sa.Column("referencia_manual", sa.String(180)),
        sa.Column("numero_fabricante", sa.String(180)),
    )
    sa.Table(
        "purchase_request_items",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_code_raw", sa.String(120)),
        sa.Column("description_raw", sa.Text),
        sa.Column("manual_reference_raw", sa.String(180)),
        sa.Column("brand_raw", sa.String(180)),
        sa.Column("manufacturer_part_number_raw", sa.String(180)),
    )
    sa.Table(
        "purchase_service_catalog",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(80)),
        sa.Column("service_name", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("specialty", sa.String(120)),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO materials (id, referencia, descricao) VALUES (1, 'MAT-01', 'Mangueira hidráulica reforçada')"))
        connection.execute(sa.text("INSERT INTO purchase_request_items (id, description_raw) VALUES (1, 'Serviço de limpeza industrial')"))
    migration = load_migration()

    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        result = connection.execute(
            sa.text(
                "SELECT entity_type, entity_id FROM purchase_search_fts "
                "WHERE purchase_search_fts MATCH :match ORDER BY entity_type"
            ),
            {"match": '"hidráulica"*'},
        ).fetchall()
        assert ("MATERIAL", 1) in result
        connection.execute(sa.text("UPDATE materials SET descricao = 'Mangueira pneumática reforçada' WHERE id = 1"))
        updated = connection.execute(
            sa.text("SELECT count(*) FROM purchase_search_fts WHERE entity_type = 'MATERIAL' AND entity_id = 1 AND purchase_search_fts MATCH :match"),
            {"match": '"pneumática"*'},
        ).scalar_one()
        assert updated == 1
        migration.downgrade()
        assert "purchase_search_fts" not in sa.inspect(connection).get_table_names()

    engine.dispose()
