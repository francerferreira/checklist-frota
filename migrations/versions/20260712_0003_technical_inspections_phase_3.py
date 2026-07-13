"""technical inspections phase 3

Revision ID: 20260712_0003
Revises: 20260712_0002
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = "20260712_0003"
down_revision = "20260712_0002"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "inspection_templates" not in tables:
        op.create_table(
            "inspection_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("family_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(20), nullable=False, server_default="RASCUNHO"),
            sa.Column("instructions", sa.Text()),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["family_id"], ["equipment_families.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.UniqueConstraint("family_id", "code", "version", name="uq_inspection_template_family_code_version"),
            sa.CheckConstraint("version > 0", name="ck_inspection_template_version_positive"),
            sa.CheckConstraint("status IN ('RASCUNHO', 'PUBLICADO', 'ARQUIVADO')", name="ck_inspection_template_status"),
        )
        for column in ("family_id", "code", "name", "version", "status", "created_by_user_id"):
            op.create_index(f"ix_inspection_templates_{column}", "inspection_templates", [column])
        tables.add("inspection_templates")
    if "inspection_template_items" not in tables:
        op.create_table(
            "inspection_template_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(80)), sa.Column("label", sa.String(180), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("response_type", sa.String(20), nullable=False, server_default="STATUS"),
            sa.Column("unit", sa.String(30)), sa.Column("minimum_value", sa.Numeric(12, 2)),
            sa.Column("maximum_value", sa.Numeric(12, 2)),
            sa.Column("evidence_on_nc", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(["template_id"], ["inspection_templates.id"]),
            sa.UniqueConstraint("template_id", "position", name="uq_inspection_template_item_position"),
            sa.CheckConstraint("position > 0", name="ck_inspection_template_item_position_positive"),
            sa.CheckConstraint("response_type IN ('STATUS', 'TEXTO', 'NUMERO')", name="ck_inspection_template_item_response_type"),
            sa.CheckConstraint("minimum_value IS NULL OR maximum_value IS NULL OR maximum_value >= minimum_value", name="ck_inspection_template_item_range"),
        )
        for column in ("template_id", "category", "label", "position", "response_type", "active"):
            op.create_index(f"ix_inspection_template_items_{column}", "inspection_template_items", [column])
        tables.add("inspection_template_items")
    if "inspection_executions" not in tables:
        op.create_table(
            "inspection_executions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("template_version", sa.Integer(), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="CONCLUIDA"),
            sa.Column("result", sa.String(20), nullable=False), sa.Column("general_notes", sa.Text()),
            sa.Column("started_at", sa.DateTime(), nullable=False), sa.Column("completed_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["template_id"], ["inspection_templates.id"]),
            sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.CheckConstraint("status IN ('CONCLUIDA')", name="ck_inspection_execution_status"),
            sa.CheckConstraint("result IN ('CONFORME', 'NAO_CONFORME')", name="ck_inspection_execution_result"),
            sa.CheckConstraint("completed_at >= started_at", name="ck_inspection_execution_period"),
        )
        for column in ("template_id", "vehicle_id", "user_id", "status", "result", "started_at", "completed_at"):
            op.create_index(f"ix_inspection_executions_{column}", "inspection_executions", [column])
        tables.add("inspection_executions")
    if "inspection_execution_items" not in tables:
        op.create_table(
            "inspection_execution_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("execution_id", sa.Integer(), nullable=False),
            sa.Column("template_item_id", sa.Integer(), nullable=False),
            sa.Column("item_label", sa.String(180), nullable=False), sa.Column("response_type", sa.String(20), nullable=False),
            sa.Column("status", sa.String(10)), sa.Column("value_text", sa.Text()),
            sa.Column("value_number", sa.Numeric(12, 2)), sa.Column("observation", sa.Text()),
            sa.Column("evidence_path", sa.String(255)),
            sa.Column("generated_non_conformity_id", sa.Integer()),
            sa.ForeignKeyConstraint(["execution_id"], ["inspection_executions.id"]),
            sa.ForeignKeyConstraint(["template_item_id"], ["inspection_template_items.id"]),
            sa.ForeignKeyConstraint(["generated_non_conformity_id"], ["mechanic_non_conformities.id"]),
            sa.UniqueConstraint("execution_id", "template_item_id", name="uq_inspection_execution_template_item"),
            sa.CheckConstraint("status IS NULL OR status IN ('OK', 'NC', 'NA')", name="ck_inspection_execution_item_status"),
        )
        for column in ("execution_id", "template_item_id", "status", "generated_non_conformity_id"):
            op.create_index(f"ix_inspection_execution_items_{column}", "inspection_execution_items", [column])


def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for name in ("inspection_execution_items", "inspection_executions", "inspection_template_items", "inspection_templates"):
        if name in tables:
            op.drop_table(name)
