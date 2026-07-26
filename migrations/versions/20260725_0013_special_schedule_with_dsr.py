"""Add Sunday and holiday schedule entries linked to DSR."""

from alembic import op
import sqlalchemy as sa


revision = "20260725_0013"
down_revision = "20260725_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_special_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("schedule_type", sa.String(length=20), nullable=False),
        sa.Column("holiday_name", sa.String(length=160), nullable=True),
        sa.Column("dsr_date", sa.Date(), nullable=False),
        sa.Column("dsr_week_start", sa.Date(), nullable=False),
        sa.Column("dsr_attendance_record_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["dsr_attendance_record_id"], ["employee_attendance_records.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.CheckConstraint("schedule_type IN ('DOMINGO', 'FERIADO')", name="ck_employee_special_schedule_type"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "schedule_date", name="uq_employee_special_schedule_day"),
        sa.UniqueConstraint("dsr_attendance_record_id"),
    )
    op.create_index("ix_employee_special_schedules_employee_id", "employee_special_schedules", ["employee_id"])
    op.create_index("ix_employee_special_schedules_schedule_date", "employee_special_schedules", ["schedule_date"])
    op.create_index("ix_employee_special_schedules_schedule_type", "employee_special_schedules", ["schedule_type"])
    op.create_index("ix_employee_special_schedules_dsr_date", "employee_special_schedules", ["dsr_date"])
    op.create_index("ix_employee_special_schedules_dsr_week_start", "employee_special_schedules", ["dsr_week_start"])
    op.create_index("ix_employee_special_schedules_created_by_user_id", "employee_special_schedules", ["created_by_user_id"])


def downgrade():
    op.drop_table("employee_special_schedules")
