"""Iscrizione/disiscrizione alle notifiche push - qualunque ruolo del tenant (owner o sotto-account)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_user
from app.config import VAPID_PUBLIC_KEY
from app.db import get_db
from app.models import PushSubscription, User

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    return {"key": VAPID_PUBLIC_KEY}


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeBody(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


@router.post("/subscribe")
async def subscribe(body: SubscribeBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))).scalar_one_or_none()
    if existing:
        existing.user_id = user.id
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth))
    await db.commit()
    return {"ok": True}


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
async def unsubscribe(body: UnsubscribeBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id))).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return {"ok": True}
