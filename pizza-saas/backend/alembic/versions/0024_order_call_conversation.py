"""id conversazione della chiamata ordine originale

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("order_call_conversation_id", sa.String(64), nullable=True))
    op.add_column("reservations", sa.Column("order_call_conversation_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("reservations", "order_call_conversation_id")
    op.drop_column("orders", "order_call_conversation_id")
