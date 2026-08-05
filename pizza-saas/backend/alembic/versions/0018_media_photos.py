"""foto attivita' per la pagina pubblica del locale

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="attivita"),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("caption", sa.String(200), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_media_photos_tenant_id", "media_photos", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_media_photos_tenant_id", table_name="media_photos")
    op.drop_table("media_photos")
