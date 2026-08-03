"""schema iniziale

Revision ID: 0001
Revises:
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Rome"),
        sa.Column("category", sa.String(32), nullable=False, server_default="pizzeria"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_kyc"),
        sa.Column("elevenlabs_agent_id", sa.String(120), nullable=True),
        sa.Column("plan", sa.String(32), nullable=False, server_default="starter"),
        sa.Column("billing_status", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("stripe_customer_id", sa.String(120), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])
    op.create_index("ix_tenants_category", "tenants", ["category"])
    op.create_index("ix_tenants_status", "tenants", ["status"])

    op.create_table(
        "admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_admin_users_email"),
        sa.UniqueConstraint("google_sub", name="uq_admin_users_google_sub"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "kyc_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_type", sa.String(64), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "offerings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("group_name", sa.String(100), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "tenant_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_hours", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("reservation_slot_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("agent_persona_name", sa.String(100), nullable=False, server_default="Assistente"),
        sa.Column("agent_tone", sa.String(32), nullable=False, server_default="amichevole"),
        sa.Column("agent_voice_id", sa.String(120), nullable=True),
        sa.Column("agent_voice_name", sa.String(120), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant"),
    )

    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("e164_number", sa.String(32), nullable=False),
        sa.Column("didww_reference", sa.String(120), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "whatsapp_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone_number_id", sa.String(64), nullable=False),
        sa.Column("waba_id", sa.String(64), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_whatsapp_channels_tenant"),
        sa.UniqueConstraint("phone_number_id", name="uq_whatsapp_channels_phone_number_id"),
    )
    op.create_index("ix_whatsapp_channels_phone_number_id", "whatsapp_channels", ["phone_number_id"])

    op.create_table(
        "bookable_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("extra", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_bookable_resources_tenant_id", "bookable_resources", ["tenant_id"])

    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bookable_resources.id"), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("customer_phone", sa.String(32), nullable=True),
        sa.Column("party_size", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="richiesta"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reservations_tenant_id", "reservations", ["tenant_id"])
    op.create_index("ix_reservations_status", "reservations", ["status"])

    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=False),
        sa.Column("history", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "customer_phone", name="uq_whatsapp_conv_tenant_phone"),
    )
    op.create_index("ix_whatsapp_conversations_tenant_id", "whatsapp_conversations", ["tenant_id"])
    op.create_index("ix_whatsapp_conversations_customer_phone", "whatsapp_conversations", ["customer_phone"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_number", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("customer_phone", sa.String(32), nullable=True),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ricevuto"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_orders_tenant_number"),
    )
    op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offering_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offerings.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("price_cents_at_order", sa.Integer(), nullable=False),
    )

    op.create_table(
        "order_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("changed_by", sa.String(255), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("order_status_history")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("whatsapp_conversations")
    op.drop_table("reservations")
    op.drop_table("bookable_resources")
    op.drop_table("whatsapp_channels")
    op.drop_table("phone_numbers")
    op.drop_table("tenant_settings")
    op.drop_table("menu_items")
    op.drop_table("kyc_documents")
    op.drop_table("users")
    op.drop_table("admin_users")
    op.drop_table("tenants")
