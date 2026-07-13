"""availability and hourmeter phase 2

Revision ID: 20260712_0002
Revises: 20260712_0001
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = "20260712_0002"
down_revision = "20260712_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "equipment_operational_states" not in existing_tables:
        op.create_table(
            "equipment_operational_states",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), nullable=False),
            sa.Column("operational_status", sa.String(length=30), nullable=False, server_default="SEM_APONTAMENTO"),
            sa.Column("status_updated_at", sa.DateTime(), nullable=True),
            sa.Column("status_reason", sa.String(length=255), nullable=True),
            sa.Column("status_evidence_path", sa.String(length=255), nullable=True),
            sa.Column("latest_hourmeter", sa.Numeric(12, 2), nullable=True),
            sa.Column("latest_hourmeter_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "operational_status IN ('SEM_APONTAMENTO', 'DISPONIVEL', 'INDISPONIVEL', 'RESTRICAO', 'MANUTENCAO')",
                name="ck_equipment_operational_state_status",
            ),
            sa.CheckConstraint(
                "latest_hourmeter IS NULL OR latest_hourmeter >= 0",
                name="ck_equipment_operational_state_hourmeter_non_negative",
            ),
            sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("vehicle_id"),
        )
        for column in ("vehicle_id", "operational_status", "status_updated_at", "latest_hourmeter_at"):
            op.create_index(f"ix_equipment_operational_states_{column}", "equipment_operational_states", [column])
        existing_tables.add("equipment_operational_states")

    if "equipment_status_events" not in existing_tables:
        op.create_table(
            "equipment_status_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("observation", sa.Text(), nullable=True),
            sa.Column("evidence_path", sa.String(length=255), nullable=True),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="MANUAL"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("status IN ('DISPONIVEL', 'INDISPONIVEL', 'RESTRICAO', 'MANUTENCAO')", name="ck_equipment_status_event_status"),
            sa.CheckConstraint("source IN ('MANUAL', 'IMPORTADO', 'AUTOMACAO', 'TELEMETRIA')", name="ck_equipment_status_event_source"),
            sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_equipment_status_event_period"),
            sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("vehicle_id", "status", "source", "started_at", "ended_at", "created_by_user_id"):
            op.create_index(f"ix_equipment_status_events_{column}", "equipment_status_events", [column])

    if "hourmeter_readings" not in existing_tables:
        op.create_table(
            "hourmeter_readings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), nullable=False),
            sa.Column("reading", sa.Numeric(12, 2), nullable=False),
            sa.Column("recorded_at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="MANUAL"),
            sa.Column("evidence_path", sa.String(length=255), nullable=True),
            sa.Column("notes", sa.String(length=255), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("reading >= 0", name="ck_hourmeter_reading_non_negative"),
            sa.CheckConstraint("source IN ('MANUAL', 'IMPORTADO', 'TELEMETRIA')", name="ck_hourmeter_reading_source"),
            sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("vehicle_id", "recorded_at", name="uq_hourmeter_vehicle_recorded_at"),
        )
        for column in ("vehicle_id", "reading", "recorded_at", "source", "created_by_user_id"):
            op.create_index(f"ix_hourmeter_readings_{column}", "hourmeter_readings", [column])

    if "equipment_operational_states" in set(sa.inspect(bind).get_table_names()):
        bind.execute(sa.text("""
            INSERT INTO equipment_operational_states
                (vehicle_id, operational_status, created_at, updated_at)
            SELECT vehicles.id, 'SEM_APONTAMENTO', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM vehicles
            LEFT JOIN equipment_operational_states states ON states.vehicle_id = vehicles.id
            WHERE states.id IS NULL
        """))


def downgrade():
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name in ("hourmeter_readings", "equipment_status_events", "equipment_operational_states"):
        if table_name in existing_tables:
            op.drop_table(table_name)
