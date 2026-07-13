"""security and governance improvements phase 9

Revision ID: 20260713_0008
Revises: 20260713_0007
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260713_0008"
down_revision = "20260713_0007"
branch_labels = None
depends_on = None


def upgrade():
    if "revoked_tokens" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("jti", name="uq_revoked_token_jti"),
    )
    for column in ("jti", "user_id", "expires_at", "revoked_at"):
        op.create_index(f"ix_revoked_tokens_{column}", "revoked_tokens", [column])


def downgrade():
    if "revoked_tokens" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("revoked_tokens")
