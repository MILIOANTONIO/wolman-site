"""connessioni social/ads del titolare (Promoziona milestone 4+)

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("external_account_id", sa.String(200), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=True),
        sa.Column("encrypted_access_token", sa.String(2000), nullable=False),
        sa.Column("encrypted_refresh_token", sa.String(2000), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="connected"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_social_connections_tenant_id", "social_connections", ["tenant_id"])

    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("username", sa.String(200), nullable=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_social_accounts_tenant_id", "social_accounts", ["tenant_id"])
    op.create_index("ix_social_accounts_connection_id", "social_accounts", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_social_accounts_connection_id", table_name="social_accounts")
    op.drop_index("ix_social_accounts_tenant_id", table_name="social_accounts")
    op.drop_table("social_accounts")
    op.drop_index("ix_social_connections_tenant_id", table_name="social_connections")
    op.drop_table("social_connections")
