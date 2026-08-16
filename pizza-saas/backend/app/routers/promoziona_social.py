"""
API connessioni social di Promoziona (milestone 4/5). Un'unica app Meta
("Wolman Promoziona" su developers.facebook.com) autentica ogni tenant
separatamente via OAuth (pattern "tech provider", spec sez. 107) - il
codice non contiene mai le credenziali del cliente, solo le sue quando le
autorizza lui stesso. TikTok/Google restano non disponibili finche' non
esistono le rispettive app sviluppatore. L'elenco provider e' onesto: mai
"connesso" se non lo e' davvero (spec sez. 76).
"""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_owner
from app.config import BACKEND_URL, FRONTEND_URL
from app.db import SessionLocal, get_db
from app.models import SocialAccount, SocialConnection, User
from app.services import social_oauth
from app.services.encryption import EncryptionNotConfigured, encrypt

router = APIRouter(prefix="/api/promoziona/social", tags=["promoziona"])

_REDIRECT_URI = f"{BACKEND_URL}/api/promoziona/social/callback/meta"
_SOCIAL_PAGE_URL = f"{FRONTEND_URL}/dashboard/viralizza/promoziona/social"


@router.get("/providers")
async def list_providers():
    return [
        {"provider": "meta", "label": "Instagram / Facebook", "available": social_oauth.is_configured()},
        {"provider": "tiktok", "label": "TikTok", "available": False},
        {"provider": "google", "label": "YouTube / Google Business", "available": False},
    ]


@router.get("/connections")
async def list_connections(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SocialConnection).where(SocialConnection.tenant_id == user.tenant_id))
    return [
        {
            "id": str(c.id), "provider": c.provider, "account_name": c.account_name, "status": c.status,
        }
        for c in result.scalars().all()
    ]


@router.get("/accounts")
async def list_accounts(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SocialAccount).where(SocialAccount.tenant_id == user.tenant_id))
    return [
        {
            "id": str(a.id), "connection_id": str(a.connection_id), "provider": a.provider,
            "type": a.type, "external_id": a.external_id, "name": a.name, "username": a.username,
            "is_selected": a.is_selected,
        }
        for a in result.scalars().all()
    ]


@router.post("/accounts/{account_id}/select")
async def toggle_account_selection(
    account_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)
):
    account = await db.get(SocialAccount, account_id)
    if not account or account.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Account non trovato")
    account.is_selected = not account.is_selected
    await db.commit()
    return {"id": str(account.id), "is_selected": account.is_selected}


@router.delete("/connections/{connection_id}")
async def disconnect(
    connection_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)
):
    connection = await db.get(SocialConnection, connection_id)
    if not connection or connection.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Connessione non trovata")
    await db.delete(connection)  # SocialAccount collegati cadono via ondelete=CASCADE
    await db.commit()
    return {"ok": True}


@router.get("/connect/meta")
async def connect_meta(user: User = Depends(get_current_owner)):
    if not social_oauth.is_configured():
        raise HTTPException(status_code=503, detail="Connessione Meta non ancora configurata")
    state = social_oauth.make_state(user.tenant_id)
    return RedirectResponse(url=social_oauth.build_authorize_url(state, _REDIRECT_URI))


@router.get("/callback/meta")
async def callback_meta(
    code: str | None = None, state: str | None = None, error: str | None = None,
    error_description: str | None = None,
):
    if error or not code or not state:
        message = error_description or error or "connessione annullata"
        return RedirectResponse(url=f"{_SOCIAL_PAGE_URL}?meta_error={message}")

    try:
        tenant_id = social_oauth.read_state(state)

        token_data = await social_oauth.exchange_code(code, _REDIRECT_URI)
        long_lived = await social_oauth.exchange_long_lived_token(token_data["access_token"])
        access_token = long_lived["access_token"]
        expires_in = long_lived.get("expires_in")

        profile = await social_oauth.fetch_user_info(access_token)
        pages = await social_oauth.fetch_pages(access_token)
        ad_accounts = await social_oauth.fetch_ad_accounts(access_token)
        encrypted_token = encrypt(access_token)
    except (social_oauth.MetaOAuthError, EncryptionNotConfigured) as e:
        return RedirectResponse(url=f"{_SOCIAL_PAGE_URL}?meta_error={e}")

    expires_at = None
    if expires_in:
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=int(expires_in))

    async with SessionLocal() as db:
        result = await db.execute(
            select(SocialConnection).where(
                SocialConnection.tenant_id == tenant_id, SocialConnection.provider == "meta"
            )
        )
        connection = result.scalar_one_or_none()
        if connection is None:
            connection = SocialConnection(tenant_id=tenant_id, provider="meta", external_account_id=profile["id"])
            db.add(connection)

        connection.external_account_id = profile["id"]
        connection.account_name = profile.get("name")
        connection.encrypted_access_token = encrypted_token
        connection.expires_at = expires_at
        connection.scopes = ",".join(social_oauth.SCOPES)
        connection.status = "connected"
        await db.flush()

        # Ripartiamo puliti ad ogni (ri)connessione: le pagine rimosse lato
        # Meta spariscono anche da noi invece di restare "fantasma" per sempre.
        await db.execute(delete(SocialAccount).where(SocialAccount.connection_id == connection.id))

        for page in pages:
            db.add(SocialAccount(
                tenant_id=tenant_id, connection_id=connection.id, provider="meta",
                external_id=page["id"], name=page.get("name"), type="page",
            ))
            ig = page.get("instagram_business_account")
            if ig:
                db.add(SocialAccount(
                    tenant_id=tenant_id, connection_id=connection.id, provider="meta",
                    external_id=ig["id"], name=page.get("name"), username=ig.get("username"),
                    type="instagram_business",
                ))
        for ad_account in ad_accounts:
            db.add(SocialAccount(
                tenant_id=tenant_id, connection_id=connection.id, provider="meta",
                external_id=ad_account["id"], name=ad_account.get("name"), type="ad_account",
            ))

        await db.commit()

    return RedirectResponse(url=f"{_SOCIAL_PAGE_URL}?meta_connected=1")
