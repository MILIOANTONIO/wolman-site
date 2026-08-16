"""link social per la sezione Viralizza > Promoziona

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("instagram_url", sa.String(300), nullable=True))
    op.add_column("tenant_settings", sa.Column("facebook_url", sa.String(300), nullable=True))
    op.add_column("tenant_settings", sa.Column("tiktok_url", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_settings", "tiktok_url")
    op.drop_column("tenant_settings", "facebook_url")
    op.drop_column("tenant_settings", "instagram_url")
