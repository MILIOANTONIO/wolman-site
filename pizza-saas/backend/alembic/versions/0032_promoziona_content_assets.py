"""libreria contenuti di Promoziona (foto/video sorgente per i Reel)

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("caption", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_content_assets_tenant_id", "content_assets", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_content_assets_tenant_id", table_name="content_assets")
    op.drop_table("content_assets")
