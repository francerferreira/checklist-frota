"""Create the server-backed notification center."""

from alembic import op
import sqlalchemy as sa


revision = "20260817_0018"
down_revision = "20260816_0017"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)} if table in _tables() else set()


def upgrade():
    if "notifications" not in _tables():
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("priority", sa.String(20), nullable=False, server_default="INFO"),
            sa.Column("origin", sa.String(60), nullable=False, server_default="SYSTEM"),
            sa.Column("entity_type", sa.String(60), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("priority IN ('INFO', 'SUCCESS', 'WARNING', 'CRITICAL')", name="ck_notifications_priority"),
        )
    for name, columns in (
        ("ix_notifications_user_id", ["user_id"]),
        ("ix_notifications_priority", ["priority"]),
        ("ix_notifications_origin", ["origin"]),
        ("ix_notifications_created_at", ["created_at"]),
        ("ix_notifications_read_at", ["read_at"]),
    ):
        if name not in _indexes("notifications"):
            op.create_index(name, "notifications", columns)


def downgrade():
    if "notifications" in _tables():
        op.drop_table("notifications")
