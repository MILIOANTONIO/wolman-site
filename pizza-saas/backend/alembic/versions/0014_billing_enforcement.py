"""sospensione/cancellazione automatica numeri per mancato pagamento: stato tenant + impostazioni piattaforma

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("past_due_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "platform_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suspend_grace_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("terminate_after_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("auto_enforcement_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
    op.drop_column("tenants", "suspended_at")
    op.drop_column("tenants", "past_due_since")
