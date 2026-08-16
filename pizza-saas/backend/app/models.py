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
    province: Mapped[str | None] = mapped_column(String(10), nullable=True)  # sigla, es. "MI"
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
    # billing_status: trial -> active -> past_due -> suspended (vedi
    # services/billing_enforcement.py). past_due_since/suspended_at segnano
    # quando e' scattato ogni passaggio, per calcolare i periodi di grazia.
    past_due_since: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    role: Mapped[str] = mapped_column(String(32), default="owner")  # owner, cuoco, receptionista, delivery
    # Ultima posizione GPS nota (solo per sotto-account "delivery" che hanno
    # attivato la condivisione posizione dal proprio telefono): usata per
    # mostrare al titolare dove si trovano i fattorini attivi su una mappa.
    # Non è uno storico tragitto, solo l'ultimo punto - basta per l'MVP.
    current_lat: Mapped[float | None] = mapped_column(nullable=True)
    current_lng: Mapped[float | None] = mapped_column(nullable=True)
    location_updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Solo per sotto-account "delivery": se non e' in servizio non riceve
    # nuovi ordini assegnati automaticamente (vedi services/orders.py).
    on_duty: Mapped[bool] = mapped_column(Boolean, default=False)
    # Presenza/attivita' del sotto-account, per mostrare al titolare chi e'
    # online in questo momento (vedi PUT /api/dashboard/heartbeat, chiamato
    # dal frontend ogni minuto mentre la dashboard e' aperta) e chi si e'
    # collegato l'ultima volta.
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)  # scelto dal titolare per la vetrina in home sulla pagina pubblica

    tenant: Mapped["Tenant"] = relationship(back_populates="offerings")


class OfferingTranslation(Base):
    """
    Traduzione salvata (EN/FR/DE/ES) di un piatto: generata via DeepL quando il
    piatto viene creato/modificato/importato, non al volo quando un visitatore
    apre la pagina - la pagina pubblica legge solo, non chiama mai DeepL.
    """
    __tablename__ = "offering_translations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offerings.id", ondelete="CASCADE"), index=True)
    lang: Mapped[str] = mapped_column(String(5))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (UniqueConstraint("offering_id", "lang", name="uq_offering_translation_offering_lang"),)


class TenantTranslation(Base):
    """Traduzione salvata (EN/FR/DE/ES) di headline/tagline/categoria della pagina pubblica, stesso principio di OfferingTranslation."""
    __tablename__ = "tenant_translations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    lang: Mapped[str] = mapped_column(String(5))
    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (UniqueConstraint("tenant_id", "lang", name="uq_tenant_translation_tenant_lang"),)


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True)
    business_hours: Mapped[dict] = mapped_column(JSON, default=dict)  # {"mon": ["12:00-14:30", "19:00-23:00"], ...}
    # Zona servita per la consegna a domicilio: raggio in km dall'indirizzo
    # del locale, più note libere per eccezioni (es. "non consegniamo oltre
    # il ponte" o elenco di quartieri/CAP specifici).
    delivery_radius_km: Mapped[float | None] = mapped_column(nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Costo di consegna addebitato al cliente sugli ordini delivery (0 =
    # consegna gratuita). Alcuni locali lo fanno pagare, altri no.
    delivery_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    # Interruttori servizi: quali capacità offrire ai clienti tramite
    # l'agente AI (voce/WhatsApp) - condizionano sia il prompt generato sia
    # cosa può fare l'agente durante l'ordine/prenotazione.
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    table_reservations_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Numero di tavoli disponibili per pranzo/cena in ogni giorno della
    # settimana, es. {"lun": {"pranzo": 8, "cena": 12}, ...} - usato
    # dall'agente per sapere quanta disponibilità comunicare (non blocca
    # ancora automaticamente le prenotazioni oltre soglia: serve solo da
    # informazione per l'AI finché non arriva un controllo disponibilità
    # reale collegato a bookable_resources/reservations).
    table_capacity: Mapped[dict] = mapped_column(JSON, default=dict)
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
    # Se valorizzati, sostituiscono il prompt generato automaticamente dal
    # template per quel canale (il proprietario può personalizzarlo a mano).
    custom_voice_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_whatsapp_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Personalizzazione del widget di chat/voce ElevenLabs da incollare sul
    # sito del cliente (vedi services/elevenlabs_agents widget) - se
    # widget_avatar_url e' vuoto, il widget usa la sfera con i due colori.
    widget_avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    widget_color_1: Mapped[str] = mapped_column(String(9), default="#e5533f")
    widget_color_2: Mapped[str] = mapped_column(String(9), default="#ff8a65")
    widget_action_text: Mapped[str] = mapped_column(String(60), default="Parla con noi")
    widget_variant: Mapped[str] = mapped_column(String(20), default="full")
    widget_placement: Mapped[str] = mapped_column(String(20), default="bottom-right")
    widget_dismissible: Mapped[bool] = mapped_column(Boolean, default=True)
    # Link ai social del locale, usati nella sezione Viralizza > Promoziona
    # per generare testi/pulsanti pronti da condividere - nessuno e' obbligatorio.
    instagram_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tiktok_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Stile scelto dal titolare per la pagina pubblica (/site/{slug}), vedi
    # Viralizza > Webapp - uno tra "rustico", "moderna", "notte", "vivace".
    # headline/tagline sono facoltativi: se vuoti la pagina usa un testo
    # generato di default a partire da nome/citta' del locale.
    public_page_template: Mapped[str] = mapped_column(String(20), default="moderna")
    public_page_headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    public_page_tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="settings")


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    e164_number: Mapped[str] = mapped_column(String(32))
    didww_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # id "phnum_..." del numero importato in ElevenLabs (vedi
    # services/elevenlabs_agents.py import_phone_number) - serve per
    # assegnare/sospendere/cancellare il numero lato ElevenLabs in seguito.
    elevenlabs_phone_number_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
    # Vedi Order.confirmation_status per il significato dei valori.
    confirmation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confirmation_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # ID della conversazione ElevenLabs DURANTE LA QUALE e' stato preso
    # l'ordine/la prenotazione (diverso da confirmation_conversation_id, che
    # e' la richiamata di conferma successiva) - usato dal webhook di fine
    # chiamata per far partire la richiamata di conferma in automatico appena
    # il cliente riaggancia, senza intervento del titolare.
    order_call_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)  # E.164, noto gia' alla prenotazione
    identity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encrypted_file_ids: Mapped[list] = mapped_column(JSON, default=list)
    verification_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # pending -> in_progress -> approved / rejected
    verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Risorsa "dids" DIDWW effettiva, nota solo dopo che l'ordine e' stato
    # provisionato (vedi services/didww_activation.py: refresh_did_activation).
    did_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # non_ordinato -> in_elaborazione -> in_verifica -> attivo (oppure bloccato/scaduto/rifiutato)
    activation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
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


class Promotion(Base):
    """
    Promozione configurata dal titolare: sconto percentuale/fisso sopra una
    soglia minima, oppure un pacchetto "paghi X prendi Y" (es. "2x3"). Il
    prezzo finale lo ricalcola sempre create_order (mai l'AI) - questa riga
    serve solo a descrivere la regola e la finestra di validità.
    """
    __tablename__ = "promotions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))  # es. "2x3 su tutte le pizze"
    promo_type: Mapped[str] = mapped_column(String(30))  # buy_x_get_y | percent_discount | fixed_discount
    # buy_x_get_y: paga buy_qty, riceve get_qty (es. 2x3 -> buy_qty=2, get_qty=3)
    buy_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    get_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # percent_discount / fixed_discount
    discount_percent: Mapped[float | None] = mapped_column(nullable=True)
    discount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)  # soglia minima opzionale (sull'intero ordine)
    applies_to_group: Mapped[str | None] = mapped_column(String(100), nullable=True)  # null = tutto il menu, altrimenti Offering.group_name
    # Piatti scelti dal titolare da mostrare come "protagonisti" della promo sulla pagina pubblica
    # (solo per la vetrina/foto - il calcolo dello sconto resta guidato da promo_type/applies_to_group).
    offering_ids: Mapped[list] = mapped_column(JSON, default=list)
    # {"lun": {"enabled": true, "from": "18:00", "to": "23:00"}, "mar": {...}, ...}
    # "from"/"to" vuoti = valida tutto il giorno. Giorno assente/enabled=false = non valida quel giorno.
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = _now()

    tenant: Mapped["Tenant"] = relationship()


class MediaPhoto(Base):
    """
    Foto libere del titolare (oggi solo "attivita": interni, esterni, piatti)
    usate nella pagina pubblica del locale - category esiste già per poter
    aggiungere sottocategorie in futuro senza migrazione.
    """
    __tablename__ = "media_photos"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(50), default="attivita")
    url: Mapped[str] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = _now()

    tenant: Mapped["Tenant"] = relationship()


class TranslationCache(Base):
    """
    Cache delle traduzioni DeepL per la pagina pubblica multilingua: stesso
    testo + stessa lingua non viene ritradotto ad ogni visita. Chiave = hash
    del testo sorgente, cosi' righe identiche di locali diversi condividono
    la cache invece di duplicarla per tenant.
    """
    __tablename__ = "translation_cache"

    id: Mapped[uuid.UUID] = _uuid_pk()
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    target_lang: Mapped[str] = mapped_column(String(5))
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = _now()

    __table_args__ = (UniqueConstraint("text_hash", "target_lang", name="uq_translation_cache_hash_lang"),)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    order_number: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))  # voice, whatsapp
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    order_type: Mapped[str] = mapped_column(String(16))  # delivery, pickup, reservation
    total_cents: Mapped[int] = mapped_column(Integer, default=0)  # gia' al netto dello sconto
    # Snapshot dello sconto applicato al momento dell'ordine (come
    # price_cents_at_order su OrderItem) - il titolo resta leggibile anche
    # se la promozione viene poi modificata o cancellata dal titolare.
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    applied_promotion_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Snapshot del costo di consegna al momento dell'ordine (0 per asporto o
    # se il locale non lo addebita) - stesso motivo dello snapshot sconto sopra.
    delivery_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    # ricevuto -> in_forno -> pronta / in_consegna -> consegnata (oppure annullato)
    status: Mapped[str] = mapped_column(String(32), default="ricevuto", index=True)
    # Solo per order_type="delivery": indirizzo raccolto dall'AI e sua
    # geocodifica (usata per l'assegnazione per vicinanza e il percorso).
    delivery_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delivery_lat: Mapped[float | None] = mapped_column(nullable=True)
    delivery_lng: Mapped[float | None] = mapped_column(nullable=True)
    # Fattorino a cui e' stato assegnato l'ordine (assegnazione automatica in
    # services/orders.py quando lo stato passa a "pronta", vedi auto_assign_order).
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Richiamata di conferma (agente vocale in uscita): null = mai chiamato,
    # "in_corso" = chiamata partita ma esito non ancora noto, "confermato"/
    # "rifiutato" = il cliente ha risposto tramite lo strumento "confirm_order",
    # "non_risponde" = la chiamata e' terminata senza che l'agente registrasse
    # una risposta (nessuna risposta, numero sbagliato, ecc.).
    confirmation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confirmation_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # ID della conversazione ElevenLabs DURANTE LA QUALE e' stato preso
    # l'ordine/la prenotazione (diverso da confirmation_conversation_id, che
    # e' la richiamata di conferma successiva) - usato dal webhook di fine
    # chiamata per far partire la richiamata di conferma in automatico appena
    # il cliente riaggancia, senza intervento del titolare.
    order_call_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class PushSubscription(Base):
    """
    Iscrizione Web Push di un browser/dispositivo per un utente (titolare o
    sotto-account): un utente può avere più iscrizioni (telefono + PC).
    L'endpoint è univoco per dispositivo/browser - reinstallare o
    re-iscriversi genera un endpoint nuovo, quello vecchio va rimosso se il
    push fallisce con 410 Gone (gestito in app/services/push.py).
    """
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = _now()


class PlatformSettings(Base):
    """
    Riga unica di impostazioni globali della piattaforma (non per-tenant):
    per ora solo il comportamento di sospensione/cancellazione numeri DIDWW
    per mancato pagamento, vedi services/billing_enforcement.py.
    """
    __tablename__ = "platform_settings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    suspend_grace_days: Mapped[int] = mapped_column(Integer, default=7)
    terminate_after_days: Mapped[int] = mapped_column(Integer, default=90)
    auto_enforcement_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ContentAsset(Base):
    """
    Libreria contenuti di Promoziona (modulo Viralizza -> Promoziona): foto/video
    sorgente caricati dal titolare, materia prima per i Reel generati - non sono
    le foto della pagina pubblica (quelle restano su MediaPhoto).
    """
    __tablename__ = "content_assets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))  # "image" | "video"
    source_url: Mapped[str] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # "ready" | "processing" | "failed"
    created_at: Mapped[datetime.datetime] = _now()

    tenant: Mapped["Tenant"] = relationship()


class Reel(Base):
    """
    Video promozionale generato da un template deterministico (milestone 2,
    mode="template") o da un provider AI foto->video (milestone 3,
    mode="ai_video", vedi app/services/video_providers.py) a partire da un
    ContentAsset. template_id e' una chiave verso TEMPLATES (data-driven, in
    app/services/video_templates.py), non una tabella - solo per mode="template".
    """
    __tablename__ = "reels"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_assets.id", ondelete="SET NULL"), nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="template")  # "template" | "ai_video"
    template_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt: Mapped[str | None] = mapped_column(String(500), nullable=True)  # solo mode="ai_video"
    # draft -> queued -> rendering -> ready | failed
    status: Mapped[str] = mapped_column(String(20), default="draft")
    duration: Mapped[int] = mapped_column(Integer, default=15)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime.datetime] = _now()
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    tenant: Mapped["Tenant"] = relationship()
    source_asset: Mapped["ContentAsset | None"] = relationship()


class ReelGeneration(Base):
    """Un tentativo di rendering per un Reel - storico/diagnostica, permette il retry senza perdere il precedente errore."""
    __tablename__ = "reel_generations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    reel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reels.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # "queued" | "rendering" | "ready" | "failed"
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = _now()
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SocialConnection(Base):
    """
    Un account social/ads collegato dal titolare (Promoziona milestone 4+):
    Meta copre sia Instagram/Facebook (pubblicazione organica) sia Meta Ads
    nella stessa connessione OAuth, TikTok/Google sono connessioni separate.
    Token SEMPRE cifrati (app/services/encryption.py) - mai in chiaro nel DB,
    mai loggati, mai esposti al frontend.
    """
    __tablename__ = "social_connections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # "meta" | "tiktok" | "google"
    external_account_id: Mapped[str] = mapped_column(String(200))
    account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    encrypted_access_token: Mapped[str] = mapped_column(String(2000))
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # connected -> needs_reauth -> disconnected (mai fallire chiamate ripetutamente in silenzio, vedi spec sez. 75)
    status: Mapped[str] = mapped_column(String(20), default="connected")
    created_at: Mapped[datetime.datetime] = _now()
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    tenant: Mapped["Tenant"] = relationship()


class SocialAccount(Base):
    """
    Asset pubblicabile dentro una SocialConnection (una Pagina Facebook puo'
    avere piu' profili Instagram collegati, un account Google Ads puo' avere
    piu' clienti, ecc. - vedi spec sez. 73, "un business puo' avere piu' Pagine").
    Il titolare sceglie quale usare, non si assume mai il primo (spec sez. 72).
    """
    __tablename__ = "social_accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_connections.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    type: Mapped[str] = mapped_column(String(30))  # "page" | "instagram_business" | "ad_account" | "channel" | "gbp_location"
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)  # scelto dal titolare per pubblicare/promuovere
    created_at: Mapped[datetime.datetime] = _now()

    tenant: Mapped["Tenant"] = relationship()
    connection: Mapped["SocialConnection"] = relationship()
