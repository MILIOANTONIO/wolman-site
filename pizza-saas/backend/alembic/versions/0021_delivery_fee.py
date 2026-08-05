"""costo di consegna configurabile

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("delivery_fee_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("delivery_fee_cents", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("orders", "delivery_fee_cents")
    op.drop_column("tenant_settings", "delivery_fee_cents")
