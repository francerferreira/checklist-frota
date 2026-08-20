"""Add catalog metadata required by the historical SC/PC/NF base."""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0022"
down_revision = "20260818_0021"
branch_labels = None
depends_on = None


def _columns(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table, column):
    if table in sa.inspect(op.get_bind()).get_table_names() and column.name not in _columns(table):
        op.add_column(table, column)


def upgrade():
    for column in (
        sa.Column("codigo_produto", sa.String(120), nullable=True),
        sa.Column("marca", sa.String(180), nullable=True),
        sa.Column("referencia_manual", sa.String(180), nullable=True),
        sa.Column("numero_fabricante", sa.String(180), nullable=True),
        sa.Column("referencia_preferencial", sa.String(180), nullable=True),
        sa.Column("status_referencia", sa.String(30), nullable=True),
        sa.Column("familia_codigo", sa.String(80), nullable=True),
        sa.Column("primeira_sc", sa.String(60), nullable=True),
        sa.Column("ultima_sc", sa.String(60), nullable=True),
        sa.Column("quantidade_registros_historicos", sa.Integer(), nullable=True),
        sa.Column("ultimo_pc", sa.String(60), nullable=True),
        sa.Column("data_ultimo_pc", sa.Date(), nullable=True),
        sa.Column("ultimo_fornecedor", sa.String(220), nullable=True),
        sa.Column("ultima_nf", sa.String(80), nullable=True),
        sa.Column("data_ultima_nf", sa.Date(), nullable=True),
        sa.Column("valor_item_ultimo_registro", sa.Numeric(18, 2), nullable=True),
    ):
        _add_column("materials", column)

    for column in (
        sa.Column("referencia_fiscal_manual", sa.String(180), nullable=True),
        sa.Column("numero_fabricante_cadastrado", sa.String(180), nullable=True),
        sa.Column("primeira_sc", sa.String(60), nullable=True),
        sa.Column("ultima_sc", sa.String(60), nullable=True),
        sa.Column("quantidade_registros_historicos", sa.Integer(), nullable=True),
        sa.Column("ultimo_fornecedor", sa.String(220), nullable=True),
        sa.Column("ultimo_pc", sa.String(60), nullable=True),
        sa.Column("ultima_observacao_sc", sa.Text(), nullable=True),
    ):
        _add_column("purchase_service_catalog", column)


def downgrade():
    for table, names in (
        ("purchase_service_catalog", ("ultima_observacao_sc", "ultimo_pc", "ultimo_fornecedor", "quantidade_registros_historicos", "ultima_sc", "primeira_sc", "numero_fabricante_cadastrado", "referencia_fiscal_manual")),
        ("materials", ("valor_item_ultimo_registro", "data_ultima_nf", "ultima_nf", "ultimo_fornecedor", "data_ultimo_pc", "ultimo_pc", "quantidade_registros_historicos", "ultima_sc", "primeira_sc", "familia_codigo", "status_referencia", "referencia_preferencial", "numero_fabricante", "referencia_manual", "marca", "codigo_produto")),
    ):
        columns = _columns(table)
        for name in names:
            if name in columns:
                op.drop_column(table, name)
