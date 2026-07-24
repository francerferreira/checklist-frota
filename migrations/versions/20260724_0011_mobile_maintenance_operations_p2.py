"""P2: permite sincronizar atualizacoes de manutencao pelo mobile."""

from alembic import op
import sqlalchemy as sa


revision = "20260724_0011"
down_revision = "20260717_0010"
branch_labels = None
depends_on = None


_OLD_TYPES = "'HORIMETRO', 'EMERGENCIA', 'OS_INICIAR', 'OS_CONCLUIR', 'OS_TESTAR', 'OS_LIBERAR'"
_NEW_TYPES = f"{_OLD_TYPES}, 'MANUTENCAO_ATUALIZAR_ITEM'"


def _replace_operation_type_constraint(allowed_types: str) -> None:
    bind = op.get_bind()
    if "mobile_sync_operations" not in sa.inspect(bind).get_table_names():
        return
    with op.batch_alter_table("mobile_sync_operations") as batch:
        batch.drop_constraint("ck_mobile_sync_operation_type", type_="check")
        batch.create_check_constraint(
            "ck_mobile_sync_operation_type",
            f"operation_type IN ({allowed_types})",
        )


def upgrade():
    _replace_operation_type_constraint(_NEW_TYPES)


def downgrade():
    bind = op.get_bind()
    if "mobile_sync_operations" in sa.inspect(bind).get_table_names():
        count = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM mobile_sync_operations "
                "WHERE operation_type = 'MANUTENCAO_ATUALIZAR_ITEM'"
            )
        ).scalar_one()
        if count:
            raise RuntimeError(
                "Downgrade bloqueado: existem atualizacoes mobile de manutencao registradas. "
                "Mantenha esta revisao para preservar os dados."
            )
    _replace_operation_type_constraint(_OLD_TYPES)
