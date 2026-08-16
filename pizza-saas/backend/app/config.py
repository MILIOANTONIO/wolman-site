"""
Configurazione centrale: legge le variabili d'ambiente dal sistema, oppure da
un file ".env.local" nella cartella backend/ (mai committato su git) — stessa
convenzione già usata in wolman-site/server/chat_server.py e
unitel-1mobile/server/webhook_server.py.
"""
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_local_env():
    path = os.path.join(BACKEND_DIR, ".env.local")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and value and key not in os.environ:
                os.environ[key] = value


_load_local_env()


def _clean_env(name, default=None):
    # I pannelli web (Render, ecc.) a volte salvano un a-capo finale se il
    # valore incollato lo conteneva: eliminarlo evita errori quando il valore
    # finisce in un header HTTP o in una stringa di connessione.
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def _to_asyncpg_url(url: str) -> str:
    # Render (e altri host) forniscono la connection string nella forma
    # "postgres://..."/"postgresql://..." pensata per client sincroni
    # (psycopg2) - il nostro engine e' async e usa asyncpg, quindi va
    # riscritta o create_async_engine prova a importare psycopg2 (non
    # installato) e va in crash all'avvio.
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _to_asyncpg_url(_clean_env("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/pizza_saas"))

SESSION_SECRET_KEY = _clean_env("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")

GOOGLE_OAUTH_CLIENT_ID = _clean_env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = _clean_env("GOOGLE_OAUTH_CLIENT_SECRET")

ANTHROPIC_API_KEY = _clean_env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _clean_env("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

DEEPL_API_KEY = _clean_env("DEEPL_API_KEY")

ELEVENLABS_API_KEY = _clean_env("ELEVENLABS_API_KEY")
ELEVENLABS_WEBHOOK_SECRET = _clean_env("ELEVENLABS_WEBHOOK_SECRET")
# Secret separato per l'header X-Tool-Secret che ElevenLabs manda sulle
# chiamate ai nostri tool (record_order, check_delivery_distance, ecc.) -
# e' il valore del segreto workspace "X-Tool-Secret" configurato lato
# ElevenLabs, NON lo stesso di ELEVENLABS_WEBHOOK_SECRET (che firma solo il
# webhook post-chiamata): sono due segreti indipendenti, ruotabili separatamente.
ELEVENLABS_TOOL_SECRET = _clean_env("ELEVENLABS_TOOL_SECRET", ELEVENLABS_WEBHOOK_SECRET)
# ID del tool "record_reservation" creato UNA VOLTA SOLA in ElevenLabs
# (Conversational AI > Tools) e riusato da tutti gli agenti tramite
# tool_ids - cosi' non serve piu' aggiungerlo a mano ad ogni agente.
ELEVENLABS_RESERVATION_TOOL_ID = _clean_env("ELEVENLABS_RESERVATION_TOOL_ID")
# ID del tool "record_order" - stesso principio del tool di prenotazione sopra,
# ma per la registrazione ordini durante la chiamata/widget.
ELEVENLABS_ORDER_TOOL_ID = _clean_env("ELEVENLABS_ORDER_TOOL_ID")
# ID del tool "check_delivery_distance" - calcola la distanza reale
# locale/cliente via Google Maps invece di farla stimare (male) al modello.
ELEVENLABS_DISTANCE_TOOL_ID = _clean_env("ELEVENLABS_DISTANCE_TOOL_ID")

# Trunk DIDWW in uscita (my.didww.com > Voice > Outbound Trunks) - condiviso
# da tutti i tenant, serve a far richiamare l'agente vocale ai clienti
# (es. ordine annullato). Il numero ElevenLabs usato come "mittente tecnico"
# e' quello gia' importato per Unitel (NUMERO MESSINA): la configurazione
# outbound e' un campo indipendente da quella inbound sulla stessa risorsa,
# quindi non tocca minimamente le chiamate in entrata di Unitel.
DIDWW_OUTBOUND_SIP_ENDPOINT = _clean_env("DIDWW_OUTBOUND_SIP_ENDPOINT")
DIDWW_OUTBOUND_SIP_USERNAME = _clean_env("DIDWW_OUTBOUND_SIP_USERNAME")
DIDWW_OUTBOUND_SIP_PASSWORD = _clean_env("DIDWW_OUTBOUND_SIP_PASSWORD")
ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID = _clean_env("ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID")
# ID dei tool "confirm_order"/"confirm_reservation" - usati SOLO durante le
# richiamate di conferma che avviamo noi (place_outbound_call), mai durante
# una chiamata in entrata normale (il prompt lo specifica esplicitamente).
ELEVENLABS_CONFIRM_ORDER_TOOL_ID = _clean_env("ELEVENLABS_CONFIRM_ORDER_TOOL_ID")
ELEVENLABS_CONFIRM_RESERVATION_TOOL_ID = _clean_env("ELEVENLABS_CONFIRM_RESERVATION_TOOL_ID")

RESEND_API_KEY = _clean_env("RESEND_API_KEY")
RESEND_URL = "https://api.resend.com/emails"
RESEND_FROM = _clean_env("RESEND_FROM", "Pizza SaaS <onboarding@resend.dev>")

WHATSAPP_APP_SECRET = _clean_env("WHATSAPP_APP_SECRET")
WHATSAPP_VERIFY_TOKEN = _clean_env("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_GRAPH_URL = "https://graph.facebook.com/v20.0"

DIDWW_API_KEY = _clean_env("DIDWW_API_KEY")
DIDWW_ENVIRONMENT = _clean_env("DIDWW_ENVIRONMENT", "sandbox")  # sandbox | production
DIDWW_BASE_URL = (
    "https://api.didww.com/v3" if DIDWW_ENVIRONMENT == "production" else "https://sandbox-api.didww.com/v3"
)

FRONTEND_URL = _clean_env("FRONTEND_URL", "http://localhost:3000")

# URL pubblico del backend stesso - Render la imposta automaticamente come
# RENDER_EXTERNAL_URL su ogni servizio, usata per costruire il redirect_uri
# OAuth di Meta (deve combaciare esattamente con quello configurato
# nell'app Meta) e per gli URL immagine passati ai provider AI esterni
# (vedi app/services/reel_queue.py). In locale non e' impostata: fallback
# a localhost, il flusso OAuth Meta funziona solo in produzione.
BACKEND_URL = _clean_env("RENDER_EXTERNAL_URL", "http://localhost:8000")

# App Meta ("Wolman Promoziona" su developers.facebook.com) usata per
# collegare Pagina Facebook/Instagram Business dei tenant - vedi
# app/services/social_oauth.py. Un'unica app per tutta la piattaforma,
# ogni tenant autorizza separatamente il proprio account (pattern
# "tech provider", spec Promoziona sez. 107).
META_APP_ID = _clean_env("META_APP_ID")
META_APP_SECRET = _clean_env("META_APP_SECRET")

# Per la geocodifica server-side dell'indirizzo di consegna (assegnazione
# fattorini per vicinanza + percorso). Deve avere "Geocoding API" abilitata
# nel progetto Google Cloud - una chiave con solo restrizione HTTP referrer
# (come quella usata dal frontend per Places/Maps JS) NON funziona qui,
# perche' le chiamate server non hanno un referrer da controllare.
GOOGLE_MAPS_API_KEY = _clean_env("GOOGLE_MAPS_API_KEY")

# Notifiche push (Web Push/VAPID). Chiave privata in formato RAW
# base64url (32 byte, NON PEM: la funzione webpush() della libreria
# pywebpush chiama internamente Vapid.from_string(), che si aspetta proprio
# questo formato e non un PEM completo, altrimenti fallisce a deserializzare
# la chiave con un errore di parsing ASN.1).
VAPID_PRIVATE_KEY_RAW = _clean_env("VAPID_PRIVATE_KEY_RAW_B64URL")
VAPID_PUBLIC_KEY = _clean_env("VAPID_PUBLIC_KEY")
VAPID_CONTACT_EMAIL = _clean_env("VAPID_CONTACT_EMAIL", "admin@example.com")
