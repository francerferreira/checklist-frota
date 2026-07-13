"""emergencies and work order lifecycle phase 4

Revision ID: 20260712_0004
Revises: 20260712_0003
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = "20260712_0004"
down_revision = "20260712_0003"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "work_order_executions" not in tables:
        op.create_table(
            "work_order_executions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("work_order_id", sa.Integer(), nullable=False),
            sa.Column("diagnosis", sa.Text()),
            sa.Column("service_performed", sa.Text()),
            sa.Column("failure_started_at", sa.DateTime(), nullable=False),
            sa.Column("repair_started_at", sa.DateTime()),
            sa.Column("repair_completed_at", sa.DateTime()),
            sa.Column("before_evidence_path", sa.String(255)),
            sa.Column("after_evidence_path", sa.String(255)),
            sa.Column("test_result", sa.String(20), nullable=False, server_default="PENDENTE"),
            sa.Column("test_notes", sa.Text()),
            sa.Column("test_evidence_path", sa.String(255)),
            sa.Column("release_status", sa.String(20), nullable=False, server_default="PENDENTE"),
            sa.Column("released_at", sa.DateTime()),
            sa.Column("released_by_user_id", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["work_order_id"], ["maintenance_work_orders.id"]),
            sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"]),
            sa.UniqueConstraint("work_order_id", name="uq_work_order_execution_work_order"),
            sa.CheckConstraint("test_result IN ('PENDENTE', 'APROVADO', 'REPROVADO')", name="ck_work_order_execution_test"),
            sa.CheckConstraint("release_status IN ('PENDENTE', 'LIBERADO', 'NAO_LIBERADO')", name="ck_work_order_execution_release"),
            sa.CheckConstraint("repair_started_at IS NULL OR repair_started_at >= failure_started_at", name="ck_work_order_execution_repair_start"),
            sa.CheckConstraint("repair_completed_at IS NULL OR repair_completed_at >= repair_started_at", name="ck_work_order_execution_repair_end"),
        )
        for column in ("work_order_id", "failure_started_at", "repair_started_at", "repair_completed_at", "test_result", "release_status", "released_at", "released_by_user_id"):
            op.create_index(f"ix_work_order_executions_{column}", "work_order_executions", [column])
        tables.add("work_order_executions")
    if "emergency_events" not in tables:
        op.create_table(
            "emergency_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_number", sa.String(40), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ABERTA"),
            sa.Column("equipment_stopped", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("location", sa.String(160)),
            sa.Column("evidence_path", sa.String(255)),
            sa.Column("reported_by_user_id", sa.Integer(), nullable=False),
            sa.Column("triaged_by_user_id", sa.Integer()),
            sa.Column("assigned_mechanic_user_id", sa.Integer()),
            sa.Column("work_order_id", sa.Integer()),
            sa.Column("opened_at", sa.DateTime(), nullable=False),
            sa.Column("acknowledged_at", sa.DateTime()),
            sa.Column("converted_at", sa.DateTime()),
            sa.Column("closed_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
            sa.ForeignKeyConstraint(["reported_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["triaged_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["assigned_mechanic_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["work_order_id"], ["maintenance_work_orders.id"]),
            sa.UniqueConstraint("event_number", name="uq_emergency_event_number"),
            sa.UniqueConstraint("work_order_id", name="uq_emergency_work_order"),
            sa.CheckConstraint("severity IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')", name="ck_emergency_severity"),
            sa.CheckConstraint("status IN ('ABERTA', 'TRIAGEM', 'CONVERTIDA', 'ENCERRADA', 'CANCELADA')", name="ck_emergency_status"),
        )
        for column in ("event_number", "vehicle_id", "severity", "status", "equipment_stopped", "reported_by_user_id", "triaged_by_user_id", "assigned_mechanic_user_id", "work_order_id", "opened_at", "title"):
            op.create_index(f"ix_emergency_events_{column}", "emergency_events", [column])


def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "emergency_events" in tables:
        op.drop_table("emergency_events")
    if "work_order_executions" in tables:
        op.drop_table("work_order_executions")
