"""motivo errore chiamata di conferma

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("confirmation_error", sa.String(200), nullable=True))
    op.add_column("reservations", sa.Column("confirmation_error", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("reservations", "confirmation_error")
    op.drop_column("orders", "confirmation_error")
