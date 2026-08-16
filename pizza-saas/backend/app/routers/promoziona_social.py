"""
API connessioni social di Promoziona (milestone 4). Solo lettura per ora:
niente flusso OAuth reale finche' non esistono le app sviluppatore
Meta/TikTok/Google (richiede identita'/azienda del titolare della
piattaforma, non e' qualcosa che il codice possa creare da solo - vedi
spec sez. 107, "PLATFORM APPROVAL REALITY"). L'elenco provider e' onesto:
mai "connesso" se non lo e' davvero (spec sez. 76).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_owner
from app.db import get_db
from app.models import SocialConnection, User

router = APIRouter(prefix="/api/promoziona/social", tags=["promoziona"])

# Provider previsti dalla spec - "available" e' falso finche' non esiste una vera app
# sviluppatore con client_id/secret configurati (vedi app/services/social_oauth.py quando
# esistera'); oggi nessuno e' disponibile, la lista serve solo a mostrare lo stato onesto.
PROVIDERS = [
    {"provider": "meta", "label": "Instagram / Facebook", "available": False},
    {"provider": "tiktok", "label": "TikTok", "available": False},
    {"provider": "google", "label": "YouTube / Google Business", "available": False},
]


@router.get("/providers")
async def list_providers():
    return PROVIDERS


@router.get("/connections")
async def list_connections(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SocialConnection).where(SocialConnection.tenant_id == user.tenant_id))
    return [
        {
            "id": str(c.id), "provider": c.provider, "account_name": c.account_name, "status": c.status,
        }
        for c in result.scalars().all()
    ]
