"""Add the MMP auxiliary stock and main-warehouse transfer tracking."""

from alembic import op
import sqlalchemy as sa


revision = "20260816_0016"
down_revision = "20260726_0015"
branch_labels = None
depends_on = None


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name, column):
    if table_name in _table_names() and column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _index_if_missing(name, table_name, columns):
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns)


def upgrade():
    _add_column("warehouses", sa.Column("warehouse_type", sa.String(20), nullable=False, server_default="PRINCIPAL"))
    _add_column("warehouse_stocks", sa.Column("location_id", sa.Integer(), nullable=True))
    _add_column("material_movements", sa.Column("warehouse_stock_id", sa.Integer(), nullable=True))
    _add_column("material_movements", sa.Column("vehicle_id", sa.Integer(), nullable=True))
    _add_column("material_movements", sa.Column("application", sa.String(160), nullable=True))

    tables = _table_names()
    if "warehouse_locations" not in tables:
        op.create_table(
            "warehouse_locations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), nullable=False),
            sa.Column("shelf_code", sa.String(40), nullable=False),
            sa.Column("location_code", sa.String(40), nullable=False),
            sa.Column("position_code", sa.String(40), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
            sa.UniqueConstraint("warehouse_id", "shelf_code", "location_code", "position_code", name="uq_warehouse_location_slot"),
        )
        for column in ("warehouse_id", "active"):
            op.create_index(f"ix_warehouse_locations_{column}", "warehouse_locations", [column])

    tables = _table_names()
    if "warehouse_transfers" not in tables:
        op.create_table(
            "warehouse_transfers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(60), nullable=False),
            sa.Column("source_warehouse_id", sa.Integer(), nullable=False),
            sa.Column("destination_warehouse_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="CONCLUIDA"),
            sa.Column("notes", sa.String(255), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_warehouse_id"], ["warehouses.id"]),
            sa.ForeignKeyConstraint(["destination_warehouse_id"], ["warehouses.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.UniqueConstraint("code", name="uq_warehouse_transfer_code"),
            sa.CheckConstraint("status IN ('RASCUNHO', 'CONCLUIDA', 'CANCELADA')", name="ck_warehouse_transfer_status"),
            sa.CheckConstraint("source_warehouse_id <> destination_warehouse_id", name="ck_warehouse_transfer_distinct_warehouses"),
        )
        for column in ("code", "source_warehouse_id", "destination_warehouse_id", "status", "created_by_user_id"):
            op.create_index(f"ix_warehouse_transfers_{column}", "warehouse_transfers", [column])

    tables = _table_names()
    if "warehouse_transfer_items" not in tables:
        op.create_table(
            "warehouse_transfer_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transfer_id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("source_stock_id", sa.Integer(), nullable=False),
            sa.Column("destination_stock_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["transfer_id"], ["warehouse_transfers.id"]),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
            sa.ForeignKeyConstraint(["source_stock_id"], ["warehouse_stocks.id"]),
            sa.ForeignKeyConstraint(["destination_stock_id"], ["warehouse_stocks.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["warehouse_locations.id"]),
            sa.CheckConstraint("quantity > 0", name="ck_warehouse_transfer_item_quantity"),
        )
        for column in ("transfer_id", "material_id", "source_stock_id", "destination_stock_id", "location_id"):
            op.create_index(f"ix_warehouse_transfer_items_{column}", "warehouse_transfer_items", [column])

    if "warehouses" in _table_names():
        _index_if_missing("ix_warehouses_warehouse_type", "warehouses", ["warehouse_type"])
    if "warehouse_stocks" in _table_names():
        _index_if_missing("ix_warehouse_stocks_location_id", "warehouse_stocks", ["location_id"])
    if "material_movements" in _table_names():
        _index_if_missing("ix_material_movements_warehouse_stock_id", "material_movements", ["warehouse_stock_id"])
        _index_if_missing("ix_material_movements_vehicle_id", "material_movements", ["vehicle_id"])


def downgrade():
    tables = _table_names()
    if "warehouse_transfer_items" in tables:
        op.drop_table("warehouse_transfer_items")
    if "warehouse_transfers" in tables:
        op.drop_table("warehouse_transfers")
    if "warehouse_locations" in tables:
        op.drop_table("warehouse_locations")
    for index_name in ("ix_material_movements_vehicle_id", "ix_material_movements_warehouse_stock_id", "ix_warehouse_stocks_location_id", "ix_warehouses_warehouse_type"):
        for table_name in ("material_movements", "warehouse_stocks", "warehouses"):
            if table_name in _table_names() and index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}:
                op.drop_index(index_name, table_name=table_name)
    for table_name, column_name in (
        ("material_movements", "application"),
        ("material_movements", "vehicle_id"),
        ("material_movements", "warehouse_stock_id"),
        ("warehouse_stocks", "location_id"),
        ("warehouses", "warehouse_type"),
    ):
        if table_name in _table_names() and column_name in _column_names(table_name):
            with op.batch_alter_table(table_name) as batch:
                batch.drop_column(column_name)
