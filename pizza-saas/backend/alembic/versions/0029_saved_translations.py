"""traduzioni salvate per piatti e headline/tagline/categoria (EN/FR/DE/ES)

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offering_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offering_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("ingredients", sa.Text, nullable=True),
        sa.Column("group_name", sa.String(100), nullable=True),
        sa.UniqueConstraint("offering_id", "lang", name="uq_offering_translation_offering_lang"),
    )
    op.create_index("ix_offering_translations_offering_id", "offering_translations", ["offering_id"])

    op.create_table(
        "tenant_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("headline", sa.String(200), nullable=True),
        sa.Column("tagline", sa.String(200), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.UniqueConstraint("tenant_id", "lang", name="uq_tenant_translation_tenant_lang"),
    )
    op.create_index("ix_tenant_translations_tenant_id", "tenant_translations", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_tenant_translations_tenant_id", table_name="tenant_translations")
    op.drop_table("tenant_translations")
    op.drop_index("ix_offering_translations_offering_id", table_name="offering_translations")
    op.drop_table("offering_translations")
