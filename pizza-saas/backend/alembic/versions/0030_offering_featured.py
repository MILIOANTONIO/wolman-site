"""piatto "in evidenza" scelto dal titolare per la vetrina in home

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offerings", sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("offerings", "is_featured")
