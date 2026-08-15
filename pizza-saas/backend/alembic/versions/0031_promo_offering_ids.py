"""piatti scelti dal titolare come protagonisti visivi di una promozione

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promotions", sa.Column("offering_ids", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("promotions", "offering_ids")
