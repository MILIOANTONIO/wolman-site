"""stato chiamata di conferma su ordini e prenotazioni

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("confirmation_status", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("confirmation_conversation_id", sa.String(64), nullable=True))
    op.add_column("reservations", sa.Column("confirmation_status", sa.String(20), nullable=True))
    op.add_column("reservations", sa.Column("confirmation_conversation_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("reservations", "confirmation_conversation_id")
    op.drop_column("reservations", "confirmation_status")
    op.drop_column("orders", "confirmation_conversation_id")
    op.drop_column("orders", "confirmation_status")
