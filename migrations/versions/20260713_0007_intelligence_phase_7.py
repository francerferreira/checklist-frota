"""executive intelligence phase 7

Revision ID: 20260713_0007
Revises: 20260713_0006
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260713_0007"
down_revision = "20260713_0006"
branch_labels = None
depends_on = None


def upgrade():
    if "automation_executions" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "automation_executions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("rule_code", sa.String(60), nullable=False), sa.Column("entity_type", sa.String(50), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False), sa.Column("dedup_key", sa.String(140), nullable=False), sa.Column("severity", sa.String(20), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"), sa.Column("message", sa.String(500), nullable=False), sa.Column("context_json", sa.Text()), sa.Column("evaluated_at", sa.DateTime(), nullable=False), sa.Column("acknowledged_at", sa.DateTime()), sa.Column("acknowledged_by_user_id", sa.Integer()), sa.Column("created_by_user_id", sa.Integer()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"]), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]), sa.UniqueConstraint("dedup_key", name="uq_automation_execution_dedup_key"), sa.CheckConstraint("severity IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')", name="ck_automation_execution_severity"), sa.CheckConstraint("status IN ('ATIVO', 'RECONHECIDO', 'ENCERRADO')", name="ck_automation_execution_status"),
    )
    for column in ("rule_code", "entity_type", "entity_id", "dedup_key", "severity", "status", "evaluated_at", "acknowledged_at", "acknowledged_by_user_id", "created_by_user_id"):
        op.create_index(f"ix_automation_executions_{column}", "automation_executions", [column])


def downgrade():
    if "automation_executions" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("automation_executions")
