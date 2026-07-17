"""Fase 3A: historico de movimentacao de localizacao dos equipamentos."""

from alembic import op
import sqlalchemy as sa


revision = "20260717_0010"
down_revision = "20260713_0009"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "equipment_location_movements" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "equipment_location_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column(
            "from_location_id",
            sa.Integer(),
            sa.ForeignKey("operational_locations.id"),
            nullable=True,
        ),
        sa.Column(
            "to_location_id",
            sa.Integer(),
            sa.ForeignKey("operational_locations.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="MANUAL"),
        sa.Column("moved_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "from_location_id IS NULL OR from_location_id <> to_location_id",
            name="ck_equipment_location_movement_distinct",
        ),
        sa.CheckConstraint(
            "source IN ('MANUAL', 'IMPORTADO', 'AUTOMACAO', 'MIGRACAO')",
            name="ck_equipment_location_movement_source",
        ),
    )
    op.create_index(
        "ix_equipment_location_movements_vehicle_id",
        "equipment_location_movements",
        ["vehicle_id"],
    )
    op.create_index(
        "ix_equipment_location_movements_from_location_id",
        "equipment_location_movements",
        ["from_location_id"],
    )
    op.create_index(
        "ix_equipment_location_movements_to_location_id",
        "equipment_location_movements",
        ["to_location_id"],
    )
    op.create_index(
        "ix_equipment_location_movements_source",
        "equipment_location_movements",
        ["source"],
    )
    op.create_index(
        "ix_equipment_location_movements_moved_at",
        "equipment_location_movements",
        ["moved_at"],
    )
    op.create_index(
        "ix_equipment_location_movements_created_by_user_id",
        "equipment_location_movements",
        ["created_by_user_id"],
    )


def downgrade():
    bind = op.get_bind()
    if "equipment_location_movements" in sa.inspect(bind).get_table_names():
        op.drop_table("equipment_location_movements")
