"""
API usate dal wizard di onboarding del proprietario: dati attività, catalogo
(offerings), risorse prenotabili (tavoli), impostazioni agente (persona,
tono, voce), upload documenti KYC, invio per revisione admin.
"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_user
from app.db import get_db
from app.models import BookableResource, KycDocument, Offering, Tenant, TenantSettings, User
from app.services import billing
from app.services.elevenlabs_agents import generate_voice_preview, list_voices
from app.services.menu_import import extract_menu_items

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "kyc")
LOGOS_DIR = os.path.join(os.path.dirname(UPLOADS_DIR), "logos")
# NOTA: disco locale va bene per l'MVP su una singola istanza; su Render
# serve un Persistent Disk montato su questo path (il filesystem di default
# è effimero e si svuota ad ogni deploy) - da configurare prima del lancio
# reale, oppure sostituire con storage S3-compatibile in fase 2.


async def _require_tenant(db: AsyncSession, user: User) -> Tenant:
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    return tenant


class BusinessInfoBody(BaseModel):
    business_name: str
    address: str | None = None
    city: str | None = None
    timezone: str = "Europe/Rome"


@router.get("/tenant")
async def get_tenant_info(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    return {
        "business_name": tenant.business_name, "address": tenant.address, "city": tenant.city,
        "logo_url": tenant.logo_url, "status": tenant.status, "plan": tenant.plan,
        "agent_persona_name": settings_row.agent_persona_name, "agent_tone": settings_row.agent_tone,
        "agent_voice_id": settings_row.agent_voice_id, "confirm_call_enabled": settings_row.confirm_call_enabled,
    }


@router.put("/business")
async def update_business_info(body: BusinessInfoBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    tenant.business_name = body.business_name
    tenant.address = body.address
    tenant.city = body.city
    tenant.timezone = body.timezone
    await db.commit()
    return {"ok": True}


@router.post("/logo")
async def upload_logo(file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ("png", "jpg", "jpeg", "webp", "svg"):
        raise HTTPException(status_code=400, detail="Formato immagine non supportato (usa PNG, JPG, WEBP o SVG)")

    tenant_dir = os.path.join(LOGOS_DIR, str(user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    filename = f"logo.{ext}"
    with open(os.path.join(tenant_dir, filename), "wb") as f:
        f.write(await file.read())

    tenant.logo_url = f"/uploads/logos/{user.tenant_id}/{filename}"
    await db.commit()
    return {"ok": True, "logo_url": tenant.logo_url}


@router.get("/plans")
async def get_plans(user: User = Depends(get_current_user)):
    return billing.PLANS


class PlanBody(BaseModel):
    plan: str


@router.put("/plan")
async def set_plan(body: PlanBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.plan not in billing.PLANS:
        raise HTTPException(status_code=400, detail="Piano non valido")
    tenant = await _require_tenant(db, user)
    tenant.plan = body.plan
    await db.commit()
    return {"ok": True, "plan": tenant.plan}


class SettingsBody(BaseModel):
    business_hours: dict = {}
    reservation_slot_minutes: int = 30
    agent_persona_name: str = "Assistente"
    agent_tone: str = "amichevole"
    agent_voice_id: str | None = None
    agent_voice_name: str | None = None
    confirm_call_enabled: bool = False


@router.put("/settings")
async def update_settings(body: SettingsBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    for field, value in body.model_dump().items():
        setattr(settings_row, field, value)
    await db.commit()
    return {"ok": True}


@router.get("/voices")
async def get_voices(user: User = Depends(get_current_user)):
    return await list_voices()


@router.get("/voices/{voice_id}/preview")
async def preview_voice(voice_id: str, user: User = Depends(get_current_user)):
    try:
        audio = await generate_voice_preview(voice_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generazione anteprima voce fallita: {e}")
    return Response(content=audio, media_type="audio/mpeg")


class OfferingBody(BaseModel):
    name: str
    description: str | None = None
    price_cents: int
    unit: str | None = None
    group_name: str | None = None
    ingredients: str | None = None
    is_available: bool = True


@router.get("/offerings")
async def list_offerings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Offering).where(Offering.tenant_id == user.tenant_id).order_by(Offering.group_name, Offering.name))
    return [_offering_dict(o) for o in result.scalars().all()]


@router.post("/offerings")
async def create_offering(body: OfferingBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    offering = Offering(tenant_id=user.tenant_id, **body.model_dump())
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    return _offering_dict(offering)


@router.put("/offerings/{offering_id}")
async def update_offering(offering_id: uuid.UUID, body: OfferingBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    offering = await db.get(Offering, offering_id)
    if not offering or offering.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Voce non trovata")
    for field, value in body.model_dump().items():
        setattr(offering, field, value)
    await db.commit()
    return _offering_dict(offering)


@router.delete("/offerings/{offering_id}")
async def delete_offering(offering_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    offering = await db.get(Offering, offering_id)
    if not offering or offering.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Voce non trovata")
    await db.delete(offering)
    await db.commit()
    return {"ok": True}


@router.post("/offerings/import")
async def import_offerings(files: list[UploadFile], user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    file_data = [(await f.read(), f.filename or "") for f in files]
    try:
        items = await extract_menu_items(file_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Estrazione menu fallita: {e}")

    if not items:
        raise HTTPException(status_code=400, detail="Nessuna voce di menu individuata nel file")

    created = []
    for item in items:
        offering = Offering(tenant_id=user.tenant_id, **item)
        db.add(offering)
        created.append(offering)
    await db.commit()
    for offering in created:
        await db.refresh(offering)

    return {"imported": len(created), "items": [_offering_dict(o) for o in created]}


def _offering_dict(o: Offering) -> dict:
    return {
        "id": str(o.id), "name": o.name, "description": o.description, "price_cents": o.price_cents,
        "unit": o.unit, "group_name": o.group_name, "ingredients": o.ingredients, "is_available": o.is_available,
    }


class ResourceBody(BaseModel):
    resource_type: str = "table"
    name: str
    capacity: int | None = None
    is_active: bool = True


@router.get("/resources")
async def list_resources(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BookableResource).where(BookableResource.tenant_id == user.tenant_id))
    return [
        {"id": str(r.id), "resource_type": r.resource_type, "name": r.name, "capacity": r.capacity, "is_active": r.is_active}
        for r in result.scalars().all()
    ]


@router.post("/resources")
async def create_resource(body: ResourceBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resource = BookableResource(tenant_id=user.tenant_id, **body.model_dump())
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return {"id": str(resource.id), "resource_type": resource.resource_type, "name": resource.name, "capacity": resource.capacity}


@router.delete("/resources/{resource_id}")
async def delete_resource(resource_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resource = await db.get(BookableResource, resource_id)
    if not resource or resource.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Risorsa non trovata")
    await db.delete(resource)
    await db.commit()
    return {"ok": True}


@router.post("/kyc-documents")
async def upload_kyc_document(doc_type: str, file: UploadFile, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tenant_dir = os.path.join(UPLOADS_DIR, str(user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest_path = os.path.join(tenant_dir, safe_name)
    with open(dest_path, "wb") as f:
        f.write(await file.read())

    doc = KycDocument(tenant_id=user.tenant_id, doc_type=doc_type, file_url=f"/uploads/kyc/{user.tenant_id}/{safe_name}")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"id": str(doc.id), "doc_type": doc.doc_type, "file_url": doc.file_url}


@router.post("/submit-for-review")
async def submit_for_review(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    if not tenant.business_name:
        raise HTTPException(status_code=400, detail="Completa prima i dati attività")

    offerings_count = (await db.execute(select(Offering).where(Offering.tenant_id == tenant.id))).scalars().first()
    if not offerings_count:
        raise HTTPException(status_code=400, detail="Aggiungi almeno una voce di menu prima di inviare")

    docs_count = (await db.execute(select(KycDocument).where(KycDocument.tenant_id == tenant.id))).scalars().first()
    if not docs_count:
        raise HTTPException(status_code=400, detail="Carica almeno un documento KYC prima di inviare")

    tenant.status = "pending_admin_review"
    await db.commit()
    return {"ok": True, "status": tenant.status}
