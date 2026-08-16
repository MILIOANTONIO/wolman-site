"""modalita' foto->video con AI per i reel (Promoziona milestone 3)

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reels", sa.Column("mode", sa.String(20), nullable=False, server_default="template"))
    op.add_column("reels", sa.Column("prompt", sa.String(500), nullable=True))
    op.alter_column("reels", "template_id", existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.alter_column("reels", "template_id", existing_type=sa.String(50), nullable=False)
    op.drop_column("reels", "prompt")
    op.drop_column("reels", "mode")
