"""logo pizzeria + toggle richiamata conferma ordine

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("tenant_settings", sa.Column("confirm_call_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("tenant_settings", "confirm_call_enabled")
    op.drop_column("tenants", "logo_url")
