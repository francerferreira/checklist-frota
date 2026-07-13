"""pcm preventive plans phase 5

Revision ID: 20260712_0005
Revises: 20260712_0004
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = "20260712_0005"
down_revision = "20260712_0004"
branch_labels = None
depends_on = None


def upgrade():
    if "preventive_plans" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "preventive_plans",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(40), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False), sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("interval_days", sa.Integer()), sa.Column("interval_hourmeter", sa.Numeric(12, 2)),
        sa.Column("tolerance_days", sa.Integer(), nullable=False, server_default="0"), sa.Column("tolerance_hourmeter", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("next_due_date", sa.Date()), sa.Column("next_due_hourmeter", sa.Numeric(12, 2)),
        sa.Column("priority", sa.String(20), nullable=False, server_default="MEDIA"), sa.Column("assigned_mechanic_user_id", sa.Integer()),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=False, server_default="60"), sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"),
        sa.Column("generation_sequence", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_generated_at", sa.DateTime()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]), sa.ForeignKeyConstraint(["assigned_mechanic_user_id"], ["users.id"]), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("code", name="uq_preventive_plan_code"),
        sa.CheckConstraint("trigger_type IN ('CALENDARIO', 'HORIMETRO', 'AMBOS')", name="ck_preventive_plan_trigger"),
        sa.CheckConstraint("priority IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')", name="ck_preventive_plan_priority"),
        sa.CheckConstraint("status IN ('ATIVO', 'PAUSADO', 'ENCERRADO')", name="ck_preventive_plan_status"),
        sa.CheckConstraint("interval_days IS NULL OR interval_days > 0", name="ck_preventive_plan_interval_days"), sa.CheckConstraint("interval_hourmeter IS NULL OR interval_hourmeter > 0", name="ck_preventive_plan_interval_hourmeter"),
        sa.CheckConstraint("tolerance_days >= 0", name="ck_preventive_plan_tolerance_days"), sa.CheckConstraint("tolerance_hourmeter >= 0", name="ck_preventive_plan_tolerance_hourmeter"), sa.CheckConstraint("estimated_duration_minutes > 0", name="ck_preventive_plan_duration"),
    )
    for column in ("code", "vehicle_id", "title", "trigger_type", "next_due_date", "next_due_hourmeter", "priority", "assigned_mechanic_user_id", "status", "created_by_user_id"):
        op.create_index(f"ix_preventive_plans_{column}", "preventive_plans", [column])


def downgrade():
    if "preventive_plans" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("preventive_plans")
