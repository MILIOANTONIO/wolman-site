"""assegnazione ordini ai fattorini: indirizzo/coordinate consegna, stato in servizio, fattorino assegnato

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("on_duty", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("users", "on_duty", server_default=None)

    op.add_column("orders", sa.Column("delivery_address", sa.String(300), nullable=True))
    op.add_column("orders", sa.Column("delivery_lat", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("delivery_lng", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_orders_assigned_to_user_id", "orders", "users",
        ["assigned_to_user_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_assigned_to_user_id", "orders", type_="foreignkey")
    op.drop_column("orders", "assigned_to_user_id")
    op.drop_column("orders", "delivery_lng")
    op.drop_column("orders", "delivery_lat")
    op.drop_column("orders", "delivery_address")
    op.drop_column("users", "on_duty")
