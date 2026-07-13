"""schema baseline

Revision ID: 20260712_0000
Revises:
Create Date: 2026-07-12 22:37:10.992408

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260712_0000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # The legacy schema already exists in deployed databases. This revision
    # gives Alembic a safe starting point without recreating or deleting data.
    return None


def downgrade():
    return None
