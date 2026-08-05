"""provincia + zona di consegna delivery

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("province", sa.String(10), nullable=True))
    op.add_column("tenant_settings", sa.Column("delivery_radius_km", sa.Float(), nullable=True))
    op.add_column("tenant_settings", sa.Column("delivery_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_settings", "delivery_notes")
    op.drop_column("tenant_settings", "delivery_radius_km")
    op.drop_column("tenants", "province")
