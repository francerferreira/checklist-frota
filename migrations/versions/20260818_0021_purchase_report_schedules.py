"""Add purchase report schedules and generated runs."""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0021"
down_revision = "20260818_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchase_report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="MONTHLY"),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("export_format", sa.String(10), nullable=False, server_default="XLSX"),
        sa.Column("filter_status", sa.String(40), nullable=True),
        sa.Column("filter_item_type", sa.String(20), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_purchase_report_schedules_next_run_at", "purchase_report_schedules", ["next_run_at"])
    op.create_index("ix_purchase_report_schedules_active", "purchase_report_schedules", ["active"])
    op.create_index("ix_purchase_report_schedules_created_by_user_id", "purchase_report_schedules", ["created_by_user_id"])
    op.create_table(
        "purchase_report_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("purchase_report_schedules.id"), nullable=True),
        sa.Column("export_format", sa.String(10), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="CONCLUIDO"),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_purchase_report_runs_schedule_id", "purchase_report_runs", ["schedule_id"])
    op.create_index("ix_purchase_report_runs_status", "purchase_report_runs", ["status"])
    op.create_index("ix_purchase_report_runs_created_by_user_id", "purchase_report_runs", ["created_by_user_id"])


def downgrade():
    op.drop_index("ix_purchase_report_runs_created_by_user_id", table_name="purchase_report_runs")
    op.drop_index("ix_purchase_report_runs_status", table_name="purchase_report_runs")
    op.drop_index("ix_purchase_report_runs_schedule_id", table_name="purchase_report_runs")
    op.drop_table("purchase_report_runs")
    op.drop_index("ix_purchase_report_schedules_created_by_user_id", table_name="purchase_report_schedules")
    op.drop_index("ix_purchase_report_schedules_active", table_name="purchase_report_schedules")
    op.drop_index("ix_purchase_report_schedules_next_run_at", table_name="purchase_report_schedules")
    op.drop_table("purchase_report_schedules")
