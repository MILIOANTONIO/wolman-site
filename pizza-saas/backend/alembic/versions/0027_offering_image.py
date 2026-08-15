"""foto opzionale per singola voce di menu

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offerings", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("offerings", "image_url")
