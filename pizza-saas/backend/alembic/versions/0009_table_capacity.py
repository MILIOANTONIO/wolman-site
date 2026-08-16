"""capacita tavoli per pranzo/cena per giorno

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("table_capacity", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("tenant_settings", "table_capacity")
