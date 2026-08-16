"""cache traduzioni DeepL per la pagina pubblica multilingua

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "translation_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("target_lang", sa.String(5), nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("translated_text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("text_hash", "target_lang", name="uq_translation_cache_hash_lang"),
    )
    op.create_index("ix_translation_cache_text_hash", "translation_cache", ["text_hash"])


def downgrade() -> None:
    op.drop_index("ix_translation_cache_text_hash", table_name="translation_cache")
    op.drop_table("translation_cache")
