"""collega phone_numbers al numero importato in ElevenLabs

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phone_numbers", sa.Column("elevenlabs_phone_number_id", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("phone_numbers", "elevenlabs_phone_number_id")
