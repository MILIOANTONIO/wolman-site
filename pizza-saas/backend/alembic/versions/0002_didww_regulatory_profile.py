"""profilo regolatorio DIDWW

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "didww_regulatory_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("available_did_id", sa.String(64), nullable=True),
        sa.Column("did_reservation_id", sa.String(64), nullable=True),
        sa.Column("sku_id", sa.String(64), nullable=True),
        sa.Column("identity_id", sa.String(64), nullable=True),
        sa.Column("address_id", sa.String(64), nullable=True),
        sa.Column("encrypted_file_ids", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("verification_id", sa.String(64), nullable=True),
        sa.Column("verification_status", sa.String(32), nullable=True),
        sa.Column("order_id", sa.String(64), nullable=True),
        sa.Column("order_status", sa.String(32), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_didww_regulatory_profiles_tenant"),
    )


def downgrade() -> None:
    op.drop_table("didww_regulatory_profiles")
