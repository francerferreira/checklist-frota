"""Fase 11: operacao mobile por ativo e sincronizacao idempotente."""

from alembic import op
import sqlalchemy as sa


revision = "20260713_0009"
down_revision = "20260713_0008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "mobile_sync_operations" in inspector.get_table_names():
        return
    op.create_table(
        "mobile_sync_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("operation_type", sa.String(length=30), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PROCESSANDO"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("conflict_reason", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("operation_type IN ('HORIMETRO', 'EMERGENCIA', 'OS_INICIAR', 'OS_CONCLUIR', 'OS_TESTAR', 'OS_LIBERAR')", name="ck_mobile_sync_operation_type"),
        sa.CheckConstraint("status IN ('PROCESSANDO', 'APLICADA', 'CONFLITO')", name="ck_mobile_sync_operation_status"),
        sa.UniqueConstraint("operation_id", name="uq_mobile_sync_operation_id"),
    )
    op.create_index("ix_mobile_sync_operations_operation_id", "mobile_sync_operations", ["operation_id"])
    op.create_index("ix_mobile_sync_operations_operation_type", "mobile_sync_operations", ["operation_type"])
    op.create_index("ix_mobile_sync_operations_vehicle_id", "mobile_sync_operations", ["vehicle_id"])
    op.create_index("ix_mobile_sync_operations_user_id", "mobile_sync_operations", ["user_id"])
    op.create_index("ix_mobile_sync_operations_status", "mobile_sync_operations", ["status"])
    op.create_index("ix_mobile_sync_operations_occurred_at", "mobile_sync_operations", ["occurred_at"])
    op.create_index("ix_mobile_sync_operations_created_at", "mobile_sync_operations", ["created_at"])
    op.create_index("ix_mobile_sync_operations_processed_at", "mobile_sync_operations", ["processed_at"])


def downgrade():
    bind = op.get_bind()
    if "mobile_sync_operations" in sa.inspect(bind).get_table_names():
        op.drop_table("mobile_sync_operations")
