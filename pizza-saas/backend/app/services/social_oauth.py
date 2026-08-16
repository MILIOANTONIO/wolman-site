"""
OAuth Meta (Facebook/Instagram) per Promoziona milestone 5: il titolare
collega la propria Pagina Facebook e l'account Instagram Business collegato.
Un'unica app Meta ("Wolman Promoziona", gestita dalla piattaforma) autentica
ogni tenant separatamente - pattern standard da "tech provider" (come
Buffer/Hootsuite), vedi spec sez. 107. Nessun secret del tenant: e' sempre
lui ad autorizzare via il dialogo OAuth di Facebook, noi non vediamo mai la
sua password.
"""
import uuid
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import META_APP_ID, META_APP_SECRET, SESSION_SECRET_KEY

GRAPH_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Scope minimi per pubblicare su Pagina/Instagram e leggere gli account
# pubblicitari collegati. ads_management/ads_read restano soggetti ad
# Advanced Access (App Review Meta) - finche' non e' approvato, Meta
# concede comunque questi scope in modalita' "Standard Access" limitata
# ai ruoli admin della app stessa (utile per i primi test).
SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
    "business_management",
    "ads_management",
    "ads_read",
]

_state_serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY, salt="promoziona-meta-oauth-state")


class MetaOAuthError(Exception):
    pass


def is_configured() -> bool:
    return bool(META_APP_ID and META_APP_SECRET)


def make_state(tenant_id: uuid.UUID) -> str:
    return _state_serializer.dumps({"tenant_id": str(tenant_id)})


def read_state(state: str) -> uuid.UUID:
    try:
        payload = _state_serializer.loads(state, max_age=600)
    except (BadSignature, SignatureExpired):
        raise MetaOAuthError("Sessione di connessione scaduta, riprova")
    return uuid.UUID(payload["tenant_id"])


def build_authorize_url(state: str, redirect_uri: str) -> str:
    params = {
        "client_id": META_APP_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": ",".join(SCOPES),
        "response_type": "code",
    }
    return f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_URL}/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
    if resp.status_code != 200:
        raise MetaOAuthError(f"Scambio codice OAuth fallito: {resp.text}")
    return resp.json()


async def exchange_long_lived_token(short_token: str) -> dict:
    """Il token utente restituito dal login scade in ~2h - lo scambiamo con
    uno "long-lived" (~60 giorni), necessario perche' l'agenzia pubblica per
    conto del cliente in giorni diversi, non solo al momento della connessione."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_URL}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": short_token,
            },
        )
    if resp.status_code != 200:
        raise MetaOAuthError(f"Rinnovo token lungo fallito: {resp.text}")
    return resp.json()


async def fetch_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{GRAPH_URL}/me", params={"access_token": access_token, "fields": "id,name"})
    if resp.status_code != 200:
        raise MetaOAuthError(f"Lettura profilo Meta fallita: {resp.text}")
    return resp.json()


async def fetch_pages(access_token: str) -> list[dict]:
    """Pagine Facebook amministrate dall'utente che ha appena autorizzato,
    con l'account Instagram Business collegato se presente."""
    pages: list[dict] = []
    url = f"{GRAPH_URL}/me/accounts"
    params = {
        "access_token": access_token,
        "fields": "id,name,access_token,instagram_business_account{id,username}",
        "limit": 100,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        while url:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise MetaOAuthError(f"Lettura pagine Facebook fallita: {resp.text}")
            data = resp.json()
            pages.extend(data.get("data", []))
            url = (data.get("paging") or {}).get("next")
            params = None  # "next" e' gia' un URL completo con i parametri
    return pages


async def fetch_ad_accounts(access_token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_URL}/me/adaccounts",
            params={"access_token": access_token, "fields": "id,name,account_status", "limit": 100},
        )
    if resp.status_code != 200:
        # Non blocca la connessione: puo' mancare ads_management (Advanced
        # Access non ancora approvato) o il tenant non avere ancora un ad
        # account - la parte organica (pagine/Instagram) resta comunque utilizzabile.
        return []
    return resp.json().get("data", [])
