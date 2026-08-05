"""promozioni: tabella promotions + sconto applicato su orders

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("promo_type", sa.String(30), nullable=False),
        sa.Column("buy_qty", sa.Integer(), nullable=True),
        sa.Column("get_qty", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Float(), nullable=True),
        sa.Column("discount_cents", sa.Integer(), nullable=True),
        sa.Column("min_order_cents", sa.Integer(), nullable=True),
        sa.Column("applies_to_group", sa.String(100), nullable=True),
        sa.Column("schedule", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_promotions_tenant_id", "promotions", ["tenant_id"])

    op.add_column("orders", sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("applied_promotion_title", sa.String(150), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "applied_promotion_title")
    op.drop_column("orders", "discount_cents")
    op.drop_index("ix_promotions_tenant_id", table_name="promotions")
    op.drop_table("promotions")
