"""Add vacation planning records for the HR module."""

from alembic import op
import sqlalchemy as sa


revision = "20260725_0012"
down_revision = "20260724_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_vacations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PROGRAMADA"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"]),
        sa.CheckConstraint("starts_on <= ends_on", name="ck_employee_vacation_period"),
        sa.CheckConstraint("status IN ('PROGRAMADA', 'APROVADA', 'CANCELADA')", name="ck_employee_vacation_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_vacations_employee_id", "employee_vacations", ["employee_id"])
    op.create_index("ix_employee_vacations_starts_on", "employee_vacations", ["starts_on"])
    op.create_index("ix_employee_vacations_ends_on", "employee_vacations", ["ends_on"])
    op.create_index("ix_employee_vacations_status", "employee_vacations", ["status"])
    op.create_index("ix_employee_vacations_created_by_user_id", "employee_vacations", ["created_by_user_id"])
    op.create_index("ix_employee_vacations_cancelled_by_user_id", "employee_vacations", ["cancelled_by_user_id"])


def downgrade():
    op.drop_table("employee_vacations")
