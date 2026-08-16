"""
API Reel di Promoziona (milestone 2): creazione da template, avvio del
rendering (accodato, mai sincrono nella richiesta HTTP - vedi
services/reel_queue.py), stato, elenco.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_owner
from app.db import get_db
from app.models import ContentAsset, Reel, User
from app.services.reel_queue import enqueue_reel
from app.services.video_templates import TEMPLATES, TEMPLATES_BY_ID

router = APIRouter(prefix="/api/promoziona", tags=["promoziona"])


class CreateReelBody(BaseModel):
    template_id: str
    source_asset_id: uuid.UUID
    caption: str | None = None


def _reel_dict(r: Reel) -> dict:
    return {
        "id": str(r.id), "template_id": r.template_id, "status": r.status,
        "duration": r.duration, "video_url": r.video_url, "thumbnail_url": r.thumbnail_url,
        "caption": r.caption, "created_at": r.created_at.isoformat(),
    }


@router.get("/templates")
async def list_templates():
    return TEMPLATES


@router.get("/reels")
async def list_reels(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reel).where(Reel.tenant_id == user.tenant_id).order_by(Reel.created_at.desc()))
    return [_reel_dict(r) for r in result.scalars().all()]


@router.get("/reels/{reel_id}")
async def get_reel(reel_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    reel = await db.get(Reel, reel_id)
    if not reel or reel.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Reel non trovato")
    return _reel_dict(reel)


@router.post("/reels")
async def create_reel(body: CreateReelBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    if body.template_id not in TEMPLATES_BY_ID:
        raise HTTPException(status_code=400, detail="Template non valido")
    asset = await db.get(ContentAsset, body.source_asset_id)
    if not asset or asset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Contenuto sorgente non trovato")

    template = TEMPLATES_BY_ID[body.template_id]
    reel = Reel(
        tenant_id=user.tenant_id, source_asset_id=asset.id, template_id=body.template_id,
        duration=template["duration"], caption=body.caption, status="draft",
    )
    db.add(reel)
    await db.commit()
    await db.refresh(reel)
    return _reel_dict(reel)


@router.post("/reels/{reel_id}/generate")
async def generate_reel(reel_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    reel = await db.get(Reel, reel_id)
    if not reel or reel.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Reel non trovato")
    if reel.status not in ("draft", "failed"):
        raise HTTPException(status_code=400, detail="Reel gia' in lavorazione o pronto")

    reel.status = "queued"
    await db.commit()
    await enqueue_reel(reel.id)
    return _reel_dict(reel)


@router.delete("/reels/{reel_id}")
async def delete_reel(reel_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    reel = await db.get(Reel, reel_id)
    if not reel or reel.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Reel non trovato")
    await db.delete(reel)
    await db.commit()
    return {"ok": True}
