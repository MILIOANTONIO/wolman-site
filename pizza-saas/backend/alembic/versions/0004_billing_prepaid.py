"""fatturazione prepagata: saldo credito, uso minuti, movimenti

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("prepaid_balance_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tenants", sa.Column("current_period_minutes_used", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tenants", sa.Column("current_period_started_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("balance_after_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_transactions_tenant_id", "credit_transactions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("credit_transactions")
    op.drop_column("tenants", "current_period_started_at")
    op.drop_column("tenants", "current_period_minutes_used")
    op.drop_column("tenants", "prepaid_balance_cents")
