"""personalizzazione widget ElevenLabs da incollare sul sito del cliente

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("widget_avatar_url", sa.String(500), nullable=True))
    op.add_column("tenant_settings", sa.Column("widget_color_1", sa.String(9), nullable=False, server_default="#e5533f"))
    op.add_column("tenant_settings", sa.Column("widget_color_2", sa.String(9), nullable=False, server_default="#ff8a65"))
    op.add_column("tenant_settings", sa.Column("widget_action_text", sa.String(60), nullable=False, server_default="Parla con noi"))
    op.add_column("tenant_settings", sa.Column("widget_variant", sa.String(20), nullable=False, server_default="full"))
    op.add_column("tenant_settings", sa.Column("widget_placement", sa.String(20), nullable=False, server_default="bottom-right"))
    op.add_column("tenant_settings", sa.Column("widget_dismissible", sa.Boolean(), nullable=False, server_default="true"))


def downgrade() -> None:
    op.drop_column("tenant_settings", "widget_dismissible")
    op.drop_column("tenant_settings", "widget_placement")
    op.drop_column("tenant_settings", "widget_variant")
    op.drop_column("tenant_settings", "widget_action_text")
    op.drop_column("tenant_settings", "widget_color_2")
    op.drop_column("tenant_settings", "widget_color_1")
    op.drop_column("tenant_settings", "widget_avatar_url")
