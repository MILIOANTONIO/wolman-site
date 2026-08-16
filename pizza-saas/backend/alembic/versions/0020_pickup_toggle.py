"""interruttore servizio: asporto

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("pickup_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("tenant_settings", "pickup_enabled")
