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
    return value.strip()


DATABASE_URL = _clean_env("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/pizza_saas")

SESSION_SECRET_KEY = _clean_env("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")

GOOGLE_OAUTH_CLIENT_ID = _clean_env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = _clean_env("GOOGLE_OAUTH_CLIENT_SECRET")

ANTHROPIC_API_KEY = _clean_env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _clean_env("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

ELEVENLABS_API_KEY = _clean_env("ELEVENLABS_API_KEY")
ELEVENLABS_WEBHOOK_SECRET = _clean_env("ELEVENLABS_WEBHOOK_SECRET")

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
