"""
Libreria contenuti di Promoziona (Viralizza -> Promoziona -> Libreria): il
titolare carica qui foto/video sorgente da usare come materia prima per i
Reel generati. Stesso schema di upload/storage di onboarding.py (disco
locale sul Persistent Disk Render montato su uploads/), directory separata
cosi' da non mischiare questi asset con le foto della pagina pubblica.
"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_owner
from app.db import get_db
from app.models import ContentAsset, User

router = APIRouter(prefix="/api/promoziona/content", tags=["promoziona"])

CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "content")

_IMAGE_EXT = ("png", "jpg", "jpeg", "webp")
_VIDEO_EXT = ("mp4", "mov", "webm")


def _asset_dict(a: ContentAsset) -> dict:
    return {
        "id": str(a.id), "type": a.type, "source_url": a.source_url,
        "thumbnail_url": a.thumbnail_url, "caption": a.caption, "status": a.status,
    }


@router.get("/assets")
async def list_assets(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContentAsset).where(ContentAsset.tenant_id == user.tenant_id).order_by(ContentAsset.created_at.desc()))
    return [_asset_dict(a) for a in result.scalars().all()]


@router.post("/assets")
async def upload_asset(file: UploadFile, caption: str | None = None, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext in _IMAGE_EXT:
        asset_type = "image"
    elif ext in _VIDEO_EXT:
        asset_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Formato non supportato (usa PNG, JPG, WEBP per foto o MP4, MOV, WEBM per video)")

    tenant_dir = os.path.join(CONTENT_DIR, str(user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(tenant_dir, filename), "wb") as f:
        f.write(await file.read())

    asset = ContentAsset(
        tenant_id=user.tenant_id, type=asset_type,
        source_url=f"/uploads/content/{user.tenant_id}/{filename}", caption=caption, status="ready",
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return _asset_dict(asset)


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    asset = await db.get(ContentAsset, asset_id)
    if not asset or asset.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Contenuto non trovato")
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), asset.source_url.lstrip("/"))
    try:
        os.remove(file_path)
    except OSError:
        pass  # file gia' assente su disco: non deve bloccare la cancellazione della riga
    await db.delete(asset)
    await db.commit()
    return {"ok": True}
