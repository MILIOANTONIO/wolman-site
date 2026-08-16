"""template/headline/tagline scelti per la pagina pubblica

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("public_page_template", sa.String(20), nullable=False, server_default="moderna"))
    op.add_column("tenant_settings", sa.Column("public_page_headline", sa.String(200), nullable=True))
    op.add_column("tenant_settings", sa.Column("public_page_tagline", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_settings", "public_page_tagline")
    op.drop_column("tenant_settings", "public_page_headline")
    op.drop_column("tenant_settings", "public_page_template")
