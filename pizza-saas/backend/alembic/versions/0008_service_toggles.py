"""interruttori servizi: delivery e prenotazione tavoli

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("delivery_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenant_settings", sa.Column("table_reservations_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("tenant_settings", "table_reservations_enabled")
    op.drop_column("tenant_settings", "delivery_enabled")
