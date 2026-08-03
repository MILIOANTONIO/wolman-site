"""
Modello dati SQLAlchemy per l'MVP pizzeria. Gli stati (tenant.status,
order.status, ecc.) sono stringhe libere validate a livello applicativo
(non enum di database) per non dover fare una migrazione ogni volta che se
ne aggiunge uno nuovo in fase di MVP.
"""
import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now():
    # timezone=True: senza questo SQLAlchemy inferisce TIMESTAMP WITHOUT TIME
    # ZONE dal type hint Python, che poi rifiuta i datetime aware (UTC) che
    # scriviamo — asyncpg lo segnala come "can't subtract offset-naive and
    # offset-aware datetimes".
    return mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Rome")
    # pizzeria oggi; hotel/idraulico/altre in fase 2 - il campo esiste già così
    # non serve una migrazione quando arrivano le prossime categorie.
    category: Mapped[str] = mapped_column(String(32), default="pizzeria", index=True)
    # pending_kyc -> pending_admin_review -> active -> suspended
    status: Mapped[str] = mapped_column(String(32), default="pending_kyc", index=True)
    elevenlabs_agent_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Piano di abbonamento (starter/growth/pro) + stato fatturazione: campi
    # segnaposto per l'integrazione Stripe di fase 2 (3 piani mensili con
    # chiamate/numero incluse, poi pay-as-you-go oltre soglia) - esistono già
    # cosi' non serve una migrazione quando quel lavoro parte.
    plan: Mapped[str] = mapped_column(String(32), default="starter")
    billing_status: Mapped[str] = mapped_column(String(32), default="trial")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Modello rigorosamente prepagato: saldo credito (mai negativo in teoria -
    # se arriva a zero l'uso extra andrebbe bloccato, non fatturato dopo).
    # Il rinnovo mensile del piano è un'azione admin manuale per ora: non
    # esiste ancora uno scheduler che addebiti automaticamente ogni mese.
    prepaid_balance_cents: Mapped[int] = mapped_column(Integer, default=0)
    current_period_minutes_used: Mapped[int] = mapped_column(Integer, default=0)
    current_period_started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = _now()

    settings: Mapped["TenantSettings"] = relationship(back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    offerings: Mapped[list["Offering"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    kyc_documents: Mapped[list["KycDocument"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    whatsapp_channel: Mapped["WhatsappChannel"] = relationship(back_populates="tenant", uselist=False, cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255), index=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="owner")  # owner
    created_at: Mapped[datetime.datetime] = _now()

    tenant: Mapped["Tenant"] = relationship(back_populates="users")

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="admin")
    created_at: Mapped[datetime.datetime] = _now()


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    doc_type: Mapped[str] = mapped_column(String(64))  # business_registration, owner_id, address_proof
    file_url: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime.datetime] = _now()
    review_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, approved, rejected
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="kyc_documents")


class Offering(Base):
    """
    Voce di catalogo generica: un piatto di menu per la pizzeria oggi, ma la
    stessa forma regge una tipologia di camera hotel o un servizio idraulico
    domani (fase 2) - niente da migrare quando cambia la categoria.
    """
    __tablename__ = "offerings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "a persona", "a notte", "a intervento"...
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # raggruppamento in UI: "Pizze", "Camere Doppie", ...
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)  # elenco libero, es. "pomodoro, mozzarella, basilico"
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="offerings")


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True)
    business_hours: Mapped[dict] = mapped_column(JSON, default=dict)  # {"mon": ["12:00-14:30", "19:00-23:00"], ...}
    # Durata slot di default per le prenotazioni (bookable_resources copre la
    # capacità/tipologia per-risorsa: tavoli, camere, ecc.)
    reservation_slot_minutes: Mapped[int] = mapped_column(Integer, default=30)
    agent_persona_name: Mapped[str] = mapped_column(String(100), default="Assistente")
    agent_tone: Mapped[str] = mapped_column(String(32), default="amichevole")
    # Voce ElevenLabs scelta dal cliente in fase di onboarding (id + nome per mostrarlo in UI)
    agent_voice_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agent_voice_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Richiamata automatica di conferma ordine: dato preparato ora, ma il
    # trigger vero e proprio non è ancora collegato - l'API ElevenLabs per
    # chiamate in uscita è documentata solo per Twilio/Exotel, non per un
    # trunk SIP generico come DIDWW (da verificare prima di attivarlo).
    confirm_call_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="settings")


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    e164_number: Mapped[str] = mapped_column(String(32))
    didww_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    assigned_at: Mapped[datetime.datetime] = _now()

    tenant: Mapped["Tenant"] = relationship(back_populates="phone_numbers")


class WhatsappChannel(Base):
    __tablename__ = "whatsapp_channels"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True)
    phone_number_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # id Meta, usato per instradare i webhook
    waba_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="whatsapp_channel")


class BookableResource(Base):
    """
    Risorsa prenotabile generica: un tavolo pizzeria oggi, una stanza hotel o
    uno slot di un idraulico domani. Il tipo di attività resta specifico
    all'MVP (pizzeria) nell'onboarding/UI/prompt; questa tabella esiste solo
    perché lo schema dati non richieda una migrazione quando arrivano le
    prossime categorie (fase 2).
    """
    __tablename__ = "bookable_resources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))  # table, room, service_slot
    name: Mapped[str] = mapped_column(String(120))  # "Tavolo 4", "Camera Doppia 12"
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # posti a sedere / ospiti max
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # campi liberi per categoria (es. piano, servizi camera)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship()
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="resource")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookable_resources.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(16))  # voice, whatsapp
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # richiesta -> confermata -> completata / annullata / no_show
    status: Mapped[str] = mapped_column(String(32), default="richiesta", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = _now()

    resource: Mapped["BookableResource"] = relationship(back_populates="reservations")


class DidwwRegulatoryProfile(Base):
    """
    Traccia il flusso di attivazione numero DIDWW per un tenant: prenotazione
    -> identità -> indirizzo -> documenti -> verifica -> ordine finale.
    Un solo profilo per tenant nell'MVP (un numero per pizzeria).
    """
    __tablename__ = "didww_regulatory_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True)
    available_did_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    did_reservation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sku_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encrypted_file_ids: Mapped[list] = mapped_column(JSON, default=list)
    verification_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # pending -> in_progress -> approved / rejected
    verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    tenant: Mapped["Tenant"] = relationship()


class CreditTransaction(Base):
    """Movimento sul credito prepagato: ricarica, canone piano, pay-as-you-go extra, rettifica manuale."""
    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32))  # topup, plan_charge, overage_charge, manual_adjustment
    amount_cents: Mapped[int] = mapped_column(Integer)  # positivo per ricariche, negativo per addebiti
    balance_after_cents: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime.datetime] = _now()


class WhatsappConversation(Base):
    """
    Cronologia messaggi per numero cliente, necessaria perché ogni webhook
    WhatsApp arriva come richiesta HTTP separata e stateless: senza questa
    tabella l'agente perderebbe il contesto tra un messaggio e l'altro.
    """
    __tablename__ = "whatsapp_conversations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    customer_phone: Mapped[str] = mapped_column(String(32), index=True)
    history: Mapped[list] = mapped_column(JSON, default=list)  # [{"role": "user"/"assistant", "content": "..."}]
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    __table_args__ = (UniqueConstraint("tenant_id", "customer_phone", name="uq_whatsapp_conv_tenant_phone"),)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    order_number: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))  # voice, whatsapp
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    order_type: Mapped[str] = mapped_column(String(16))  # delivery, pickup, reservation
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    # ricevuto -> in_forno -> pronta / in_consegna -> consegnata (oppure annullato)
    status: Mapped[str] = mapped_column(String(32), default="ricevuto", index=True)
    created_at: Mapped[datetime.datetime] = _now()
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("tenant_id", "order_number", name="uq_orders_tenant_number"),)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offerings.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents_at_order: Mapped[int] = mapped_column(Integer)  # prezzo al momento dell'ordine, non ricalcolato dopo

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32))
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime.datetime] = _now()
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped["Order"] = relationship(back_populates="status_history")
