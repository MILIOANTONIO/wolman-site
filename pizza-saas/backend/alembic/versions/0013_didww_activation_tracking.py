"""traccia l'attivazione reale del numero DIDWW (dids resource), non solo l'ordine

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("didww_regulatory_profiles", sa.Column("phone_number", sa.String(32), nullable=True))
    op.add_column("didww_regulatory_profiles", sa.Column("verification_reject_reason", sa.Text(), nullable=True))
    op.add_column("didww_regulatory_profiles", sa.Column("did_id", sa.String(64), nullable=True))
    op.add_column("didww_regulatory_profiles", sa.Column("activation_status", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("didww_regulatory_profiles", "activation_status")
    op.drop_column("didww_regulatory_profiles", "did_id")
    op.drop_column("didww_regulatory_profiles", "verification_reject_reason")
    op.drop_column("didww_regulatory_profiles", "phone_number")
