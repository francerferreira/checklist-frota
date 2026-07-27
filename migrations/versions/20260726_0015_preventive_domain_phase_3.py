"""Fase 3: estrutura complementar para preventivas e rastreabilidade.

Esta migration é aditiva. Ela reaproveita as tabelas existentes de equipamentos,
horímetro, planos preventivos, materiais e ordens de serviço, sem duplicá-las.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_0015"
down_revision = "20260726_0014"
branch_labels = None
depends_on = None


HOURMETER_COLUMNS = {
    "previous_reading": sa.Numeric(12, 2),
    "difference_hours": sa.Numeric(12, 2),
    "validation_status": sa.String(20),
    "exception_justification": sa.Text(),
    "cancelled_at": sa.DateTime(),
    "cancelled_by_user_id": sa.Integer(),
    "cancellation_reason": sa.Text(),
    "replacement_reading_id": sa.Integer(),
}


AUDIT_COLUMNS = {
    "module": sa.String(80),
    "equipment_id": sa.Integer(),
    "record_id": sa.Integer(),
    "justification": sa.Text(),
    "origin": sa.String(30),
    "ip_address": sa.String(64),
    "device": sa.String(120),
}


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _add_columns(table_name, columns):
    if table_name not in _table_names():
        return
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
    for name, column in columns.items():
        if name not in existing:
            op.add_column(table_name, sa.Column(name, column, nullable=True))


def upgrade():
    # Mantém a leitura de horímetro auditável sem alterar os campos já usados
    # pelo aplicativo (vehicle_id, reading e recorded_at).
    _add_columns("hourmeter_readings", HOURMETER_COLUMNS)

    # O audit_logs pertence ao legado e pode não existir em uma instalação
    # recém-criada. Quando existir, apenas ampliamos sua capacidade.
    _add_columns("audit_logs", AUDIT_COLUMNS)

    tables = _table_names()
    if "preventive_executions" not in tables:
        op.create_table(
            "preventive_executions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("vehicle_id", sa.Integer(), nullable=False),
            sa.Column("preventive_plan_id", sa.Integer(), nullable=False),
            sa.Column("cycle_hourmeter", sa.Numeric(12, 2), nullable=True),
            sa.Column("hourmeter_start", sa.Numeric(12, 2), nullable=True),
            sa.Column("hourmeter_execution", sa.Numeric(12, 2), nullable=True),
            sa.Column("scheduled_date", sa.Date(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PLANEJADA"),
            sa.Column("responsible_user_id", sa.Integer(), nullable=True),
            sa.Column("work_order_id", sa.Integer(), nullable=True),
            sa.Column("observation", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
            sa.ForeignKeyConstraint(["preventive_plan_id"], ["preventive_plans.id"]),
            sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["work_order_id"], ["maintenance_work_orders.id"]),
            sa.CheckConstraint(
                "status IN ('PLANEJADA', 'PROGRAMADA', 'EM_EXECUCAO', 'CONCLUIDA', 'CANCELADA', 'NAO_EXECUTADA')",
                name="ck_preventive_execution_status",
            ),
            sa.CheckConstraint("cycle_hourmeter IS NULL OR cycle_hourmeter >= 0", name="ck_preventive_execution_cycle"),
            sa.CheckConstraint("hourmeter_start IS NULL OR hourmeter_start >= 0", name="ck_preventive_execution_start"),
            sa.CheckConstraint("hourmeter_execution IS NULL OR hourmeter_execution >= 0", name="ck_preventive_execution_reading"),
        )
        for column in (
            "vehicle_id",
            "preventive_plan_id",
            "scheduled_date",
            "status",
            "responsible_user_id",
            "work_order_id",
            "created_at",
        ):
            op.create_index(f"ix_preventive_executions_{column}", "preventive_executions", [column])

    tables = _table_names()
    if "preventive_stages" not in tables:
        op.create_table(
            "preventive_stages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("preventive_execution_id", sa.Integer(), nullable=False),
            sa.Column("stage_type", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDENTE"),
            sa.Column("percent_complete", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("responsible_user_id", sa.Integer(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("observation", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["preventive_execution_id"], ["preventive_executions.id"]),
            sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"]),
            sa.CheckConstraint(
                "stage_type IN ('MOTOR', 'ELETRICA', 'LUBRIFICACAO', 'ESTRUTURAL', 'INSPECAO', 'CHECKLIST', 'TESTE_OPERACIONAL')",
                name="ck_preventive_stage_type",
            ),
            sa.CheckConstraint("status IN ('PENDENTE', 'EM_EXECUCAO', 'CONCLUIDA', 'BLOQUEADA', 'NAO_EXECUTADA')", name="ck_preventive_stage_status"),
            sa.CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_preventive_stage_percent"),
            sa.UniqueConstraint("preventive_execution_id", "stage_type", name="uq_preventive_stage_type"),
        )
        for column in ("preventive_execution_id", "stage_type", "status", "responsible_user_id"):
            op.create_index(f"ix_preventive_stages_{column}", "preventive_stages", [column])

    tables = _table_names()
    if "preventive_materials" not in tables:
        op.create_table(
            "preventive_materials",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("preventive_execution_id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("quantity_planned", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("quantity_separated", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("quantity_used", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="SOLICITADO"),
            sa.Column("requested_at", sa.DateTime(), nullable=True),
            sa.Column("separated_at", sa.DateTime(), nullable=True),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("observation", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["preventive_execution_id"], ["preventive_executions.id"]),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
            sa.CheckConstraint("quantity_planned >= 0", name="ck_preventive_material_planned"),
            sa.CheckConstraint("quantity_separated >= 0 AND quantity_separated <= quantity_planned", name="ck_preventive_material_separated"),
            sa.CheckConstraint("quantity_used >= 0 AND quantity_used <= quantity_separated", name="ck_preventive_material_used"),
            sa.CheckConstraint("status IN ('SOLICITADO', 'SEPARADO', 'UTILIZADO', 'CANCELADO')", name="ck_preventive_material_status"),
            sa.UniqueConstraint("preventive_execution_id", "material_id", name="uq_preventive_material"),
        )
        for column in ("preventive_execution_id", "material_id", "status"):
            op.create_index(f"ix_preventive_materials_{column}", "preventive_materials", [column])


def _drop_added_columns(table_name, columns):
    if table_name not in _table_names():
        return
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
    removable = [name for name in columns if name in existing]
    if not removable:
        return
    with op.batch_alter_table(table_name) as batch:
        for name in removable:
            batch.drop_column(name)


def downgrade():
    # Removemos primeiro as tabelas dependentes. Os dados operacionais legados
    # (equipamentos, planos, materiais e OS) nunca são apagados por esta fase.
    tables = _table_names()
    for table_name in ("preventive_materials", "preventive_stages", "preventive_executions"):
        if table_name in tables:
            op.drop_table(table_name)
    _drop_added_columns("audit_logs", AUDIT_COLUMNS)
    _drop_added_columns("hourmeter_readings", HOURMETER_COLUMNS)
