"""posizione GPS ultima nota per i sotto-account delivery

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("current_lat", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("current_lng", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "location_updated_at")
    op.drop_column("users", "current_lng")
    op.drop_column("users", "current_lat")
