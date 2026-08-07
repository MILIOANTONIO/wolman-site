"""
API usate dal wizard di onboarding del proprietario: dati attività, catalogo
(offerings), risorse prenotabili (tavoli), impostazioni agente (persona,
tono, voce), upload documenti KYC, invio per revisione admin.
"""
import os
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_owner
from app.db import get_db
from app.models import BookableResource, DidwwRegulatoryProfile, KycDocument, MediaPhoto, Offering, Promotion, Tenant, TenantSettings, User
from app.services import billing, didww_client, didww_geo
from app.services.didww_activation import refresh_did_activation
from app.services.elevenlabs_agents import generate_voice_preview, list_voices, update_agent
from app.services.menu_import import extract_menu_items
from app.services.prompt_builder import build_agent_prompt

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "kyc")
LOGOS_DIR = os.path.join(os.path.dirname(UPLOADS_DIR), "logos")
MEDIA_DIR = os.path.join(os.path.dirname(UPLOADS_DIR), "media")
# NOTA: disco locale va bene per l'MVP su una singola istanza; su Render
# serve un Persistent Disk montato su questo path (il filesystem di default
# è effimero e si svuota ad ogni deploy) - da configurare prima del lancio
# reale, oppure sostituire con storage S3-compatibile in fase 2.


async def _require_tenant(db: AsyncSession, user: User) -> Tenant:
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant non trovato")
    return tenant


async def _sync_agent(db: AsyncSession, tenant: Tenant) -> bool:
    """Ripubblica il prompt (menu/orari/servizi/persona/voce sono tutti
    generati dentro build_agent_prompt) sull'agente ElevenLabs gia' esistente,
    cosi' una modifica in dashboard si sente alla prossima chiamata invece di
    restare "congelata" nella versione del prompt dell'ultima approvazione.
    Fallisce in modo silenzioso (solo log) - non deve bloccare il salvataggio
    di dati che di per se' sono gia' andati a buon fine nel nostro DB."""
    if not tenant.elevenlabs_agent_id:
        return False
    try:
        settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
        prompt = await build_agent_prompt(db, tenant, channel="voice")
        first_message = f"Ciao, grazie per aver chiamato {tenant.business_name}! Come posso aiutarti?"
        await update_agent(
            tenant.elevenlabs_agent_id, name=f"{tenant.business_name} - {settings_row.agent_persona_name}",
            prompt=prompt, first_message=first_message, voice_id=settings_row.agent_voice_id,
        )
        return True
    except Exception as e:
        sys.stderr.write(f"Aggiornamento agente ElevenLabs fallito per tenant {tenant.id}: {e}\n")
        return False


class BusinessInfoBody(BaseModel):
    business_name: str
    address: str | None = None
    city: str | None = None
    province: str | None = None
    category: str = "pizzeria"  # pizzeria, ristorante
    timezone: str = "Europe/Rome"


@router.get("/tenant")
async def get_tenant_info(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    return {
        "business_name": tenant.business_name, "slug": tenant.slug, "address": tenant.address, "city": tenant.city, "province": tenant.province,
        "category": tenant.category,
        "logo_url": tenant.logo_url, "status": tenant.status, "plan": tenant.plan,
        "elevenlabs_agent_id": tenant.elevenlabs_agent_id,
        "agent_persona_name": settings_row.agent_persona_name, "agent_tone": settings_row.agent_tone,
        "agent_voice_id": settings_row.agent_voice_id, "confirm_call_enabled": settings_row.confirm_call_enabled,
        "business_hours": settings_row.business_hours or {},
        "delivery_radius_km": settings_row.delivery_radius_km, "delivery_notes": settings_row.delivery_notes,
        "delivery_fee_cents": settings_row.delivery_fee_cents,
        "delivery_enabled": settings_row.delivery_enabled, "pickup_enabled": settings_row.pickup_enabled,
        "table_reservations_enabled": settings_row.table_reservations_enabled,
        "table_capacity": settings_row.table_capacity or {},
    }


@router.put("/business")
async def update_business_info(body: BusinessInfoBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    tenant.business_name = body.business_name
    tenant.address = body.address
    tenant.city = body.city
    tenant.province = body.province
    tenant.category = body.category
    tenant.timezone = body.timezone
    await db.commit()
    pushed = await _sync_agent(db, tenant)
    return {"ok": True, "pushed_to_elevenlabs": pushed}


class DeliveryZoneBody(BaseModel):
    delivery_radius_km: float | None = None
    delivery_notes: str | None = None
    delivery_fee_cents: int = 0


@router.put("/delivery-zone")
async def update_delivery_zone(body: DeliveryZoneBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    if body.delivery_fee_cents < 0:
        raise HTTPException(status_code=400, detail="Il costo di consegna non può essere negativo")
    tenant = await _require_tenant(db, user)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    settings_row.delivery_radius_km = body.delivery_radius_km
    settings_row.delivery_notes = body.delivery_notes
    settings_row.delivery_fee_cents = body.delivery_fee_cents
    await db.commit()
    pushed = await _sync_agent(db, tenant)
    return {"ok": True, "pushed_to_elevenlabs": pushed}


class ServicesBody(BaseModel):
    delivery_enabled: bool
    pickup_enabled: bool
    table_reservations_enabled: bool


@router.put("/services")
async def update_services(body: ServicesBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    settings_row.delivery_enabled = body.delivery_enabled
    settings_row.pickup_enabled = body.pickup_enabled
    settings_row.table_reservations_enabled = body.table_reservations_enabled
    await db.commit()
    pushed = await _sync_agent(db, tenant)
    return {"ok": True, "pushed_to_elevenlabs": pushed}


class TableCapacityBody(BaseModel):
    # {"lun": {"pranzo": {"tables": 5, "seats": 20}, "cena": {"tables": 8, "seats": 32}}, ...}
    table_capacity: dict[str, dict[str, dict[str, int]]]


@router.put("/table-capacity")
async def update_table_capacity(body: TableCapacityBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    settings_row.table_capacity = body.table_capacity
    await db.commit()
    pushed = await _sync_agent(db, tenant)
    return {"ok": True, "pushed_to_elevenlabs": pushed}


@router.post("/logo")
async def upload_logo(file: UploadFile, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
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


class WidgetSettingsBody(BaseModel):
    widget_color_1: str = "#e5533f"
    widget_color_2: str = "#ff8a65"
    widget_action_text: str = "Parla con noi"
    widget_variant: str = "full"
    widget_placement: str = "bottom-right"
    widget_dismissible: bool = True


def _widget_dict(s: TenantSettings) -> dict:
    return {
        "widget_avatar_url": s.widget_avatar_url,
        "widget_color_1": s.widget_color_1, "widget_color_2": s.widget_color_2,
        "widget_action_text": s.widget_action_text, "widget_variant": s.widget_variant,
        "widget_placement": s.widget_placement, "widget_dismissible": s.widget_dismissible,
    }


@router.get("/widget-settings")
async def get_widget_settings(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    return _widget_dict(settings_row)


@router.put("/widget-settings")
async def update_widget_settings(body: WidgetSettingsBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    for field, value in body.model_dump().items():
        setattr(settings_row, field, value)
    await db.commit()
    return _widget_dict(settings_row)


class SocialLinksBody(BaseModel):
    instagram_url: str | None = None
    facebook_url: str | None = None
    tiktok_url: str | None = None


@router.get("/social-links")
async def get_social_links(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    return {"instagram_url": settings_row.instagram_url, "facebook_url": settings_row.facebook_url, "tiktok_url": settings_row.tiktok_url}


@router.put("/social-links")
async def update_social_links(body: SocialLinksBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    settings_row.instagram_url = body.instagram_url or None
    settings_row.facebook_url = body.facebook_url or None
    settings_row.tiktok_url = body.tiktok_url or None
    await db.commit()
    return {"instagram_url": settings_row.instagram_url, "facebook_url": settings_row.facebook_url, "tiktok_url": settings_row.tiktok_url}


class PageDesignBody(BaseModel):
    public_page_template: str = "moderna"
    public_page_headline: str | None = None
    public_page_tagline: str | None = None


_PAGE_TEMPLATES = {"rustico", "moderna", "notte", "vivace"}


def _page_design_dict(s: TenantSettings) -> dict:
    return {
        "public_page_template": s.public_page_template,
        "public_page_headline": s.public_page_headline,
        "public_page_tagline": s.public_page_tagline,
    }


@router.get("/page-design")
async def get_page_design(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    return _page_design_dict(settings_row)


@router.put("/page-design")
async def update_page_design(body: PageDesignBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    if body.public_page_template not in _PAGE_TEMPLATES:
        raise HTTPException(status_code=400, detail="Template non valido")
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    settings_row.public_page_template = body.public_page_template
    settings_row.public_page_headline = body.public_page_headline or None
    settings_row.public_page_tagline = body.public_page_tagline or None
    await db.commit()
    return _page_design_dict(settings_row)


@router.post("/widget-avatar")
async def upload_widget_avatar(file: UploadFile, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ("png", "jpg", "jpeg", "webp"):
        raise HTTPException(status_code=400, detail="Formato immagine non supportato (usa PNG, JPG o WEBP)")

    tenant_dir = os.path.join(MEDIA_DIR, str(user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    filename = f"widget-avatar.{ext}"
    with open(os.path.join(tenant_dir, filename), "wb") as f:
        f.write(await file.read())

    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    settings_row.widget_avatar_url = f"/uploads/media/{user.tenant_id}/{filename}"
    await db.commit()
    return {"ok": True, "widget_avatar_url": settings_row.widget_avatar_url}


@router.delete("/widget-avatar")
async def delete_widget_avatar(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    settings_row.widget_avatar_url = None
    await db.commit()
    return {"ok": True}


def _photo_dict(p: MediaPhoto) -> dict:
    return {"id": str(p.id), "category": p.category, "url": p.url, "caption": p.caption, "position": p.position}


@router.get("/media-photos")
async def list_media_photos(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MediaPhoto).where(MediaPhoto.tenant_id == user.tenant_id).order_by(MediaPhoto.position, MediaPhoto.created_at))
    return [_photo_dict(p) for p in result.scalars().all()]


@router.post("/media-photos")
async def upload_media_photo(file: UploadFile, caption: str | None = None, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ("png", "jpg", "jpeg", "webp"):
        raise HTTPException(status_code=400, detail="Formato immagine non supportato (usa PNG, JPG o WEBP)")

    count = (await db.execute(select(func.count()).select_from(MediaPhoto).where(MediaPhoto.tenant_id == user.tenant_id))).scalar_one()
    tenant_dir = os.path.join(MEDIA_DIR, str(user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(tenant_dir, filename), "wb") as f:
        f.write(await file.read())

    photo = MediaPhoto(
        tenant_id=user.tenant_id, category="attivita",
        url=f"/uploads/media/{user.tenant_id}/{filename}", caption=caption, position=count,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return _photo_dict(photo)


@router.delete("/media-photos/{photo_id}")
async def delete_media_photo(photo_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    photo = await db.get(MediaPhoto, photo_id)
    if not photo or photo.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Foto non trovata")
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), photo.url.lstrip("/"))
    try:
        os.remove(file_path)
    except OSError:
        pass  # file già assente su disco: non deve bloccare la cancellazione della riga
    await db.delete(photo)
    await db.commit()
    return {"ok": True}


@router.get("/plans")
async def get_plans(user: User = Depends(get_current_owner)):
    return billing.PLANS


class PlanBody(BaseModel):
    plan: str


@router.put("/plan")
async def set_plan(body: PlanBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    if body.plan not in billing.PLANS:
        raise HTTPException(status_code=400, detail="Piano non valido")
    tenant = await _require_tenant(db, user)
    tenant.plan = body.plan
    await db.commit()
    return {"ok": True, "plan": tenant.plan}


class BusinessHoursBody(BaseModel):
    business_hours: dict  # {"lun": ["12:00-14:30", "19:00-23:00"], "mar": [], ...} lista vuota = chiuso


@router.put("/business-hours")
async def update_business_hours(body: BusinessHoursBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    settings_row.business_hours = body.business_hours
    await db.commit()
    pushed = await _sync_agent(db, tenant)
    return {"ok": True, "pushed_to_elevenlabs": pushed}


class SettingsBody(BaseModel):
    business_hours: dict = {}
    reservation_slot_minutes: int = 30
    agent_persona_name: str = "Assistente"
    agent_tone: str = "amichevole"
    agent_voice_id: str | None = None
    agent_voice_name: str | None = None
    confirm_call_enabled: bool = False


@router.put("/settings")
async def update_settings(body: SettingsBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()
    for field, value in body.model_dump().items():
        setattr(settings_row, field, value)
    await db.commit()

    tenant = await db.get(Tenant, user.tenant_id)
    pushed_to_elevenlabs = False
    if tenant.elevenlabs_agent_id:
        # Tenant gia' approvato: persona/tono/voce cambiano il prompt e la
        # voce dell'agente, quindi vanno ripubblicati subito su ElevenLabs -
        # altrimenti la chiamata vera continua a usare la configurazione
        # vecchia finche' qualcuno non tocca un altro campo che lo fa (es.
        # il prompt personalizzato).
        try:
            prompt = await build_agent_prompt(db, tenant, channel="voice")
            first_message = f"Ciao, grazie per aver chiamato {tenant.business_name}! Come posso aiutarti?"
            await update_agent(
                tenant.elevenlabs_agent_id, name=f"{tenant.business_name} - {settings_row.agent_persona_name}",
                prompt=prompt, first_message=first_message, voice_id=settings_row.agent_voice_id,
            )
            pushed_to_elevenlabs = True
        except Exception as e:
            sys.stderr.write(f"Aggiornamento impostazioni su ElevenLabs fallito per tenant {user.tenant_id}: {e}\n")
            raise HTTPException(status_code=502, detail="Impostazioni salvate, ma l'aggiornamento su ElevenLabs è fallito - riprova")

    return {"ok": True, "pushed_to_elevenlabs": pushed_to_elevenlabs}


@router.get("/voices")
async def get_voices(user: User = Depends(get_current_owner)):
    return await list_voices()


@router.get("/voices/{voice_id}/preview")
async def preview_voice(voice_id: str, user: User = Depends(get_current_owner)):
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
async def list_offerings(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Offering).where(Offering.tenant_id == user.tenant_id).order_by(Offering.group_name, Offering.name))
    return [_offering_dict(o) for o in result.scalars().all()]


@router.post("/offerings")
async def create_offering(body: OfferingBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    offering = Offering(tenant_id=user.tenant_id, **body.model_dump())
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    await _sync_agent(db, tenant)
    return _offering_dict(offering)


@router.put("/offerings/{offering_id}")
async def update_offering(offering_id: uuid.UUID, body: OfferingBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    offering = await db.get(Offering, offering_id)
    if not offering or offering.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Voce non trovata")
    for field, value in body.model_dump().items():
        setattr(offering, field, value)
    await db.commit()
    await _sync_agent(db, tenant)
    return _offering_dict(offering)


@router.delete("/offerings/{offering_id}")
async def delete_offering(offering_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    offering = await db.get(Offering, offering_id)
    if not offering or offering.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Voce non trovata")
    await db.delete(offering)
    await db.commit()
    await _sync_agent(db, tenant)
    return {"ok": True}


@router.post("/offerings/import")
async def import_offerings(files: list[UploadFile], user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
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
    await _sync_agent(db, tenant)

    return {"imported": len(created), "items": [_offering_dict(o) for o in created]}


def _offering_dict(o: Offering) -> dict:
    return {
        "id": str(o.id), "name": o.name, "description": o.description, "price_cents": o.price_cents,
        "unit": o.unit, "group_name": o.group_name, "ingredients": o.ingredients, "is_available": o.is_available,
    }


class PromotionBody(BaseModel):
    title: str
    promo_type: str  # buy_x_get_y | percent_discount | fixed_discount
    buy_qty: int | None = None
    get_qty: int | None = None
    discount_percent: float | None = None
    discount_cents: int | None = None
    min_order_cents: int | None = None
    applies_to_group: str | None = None
    schedule: dict = {}  # {"lun": {"enabled": true, "from": "18:00", "to": "23:00"}, ...}
    is_active: bool = True


def _promotion_dict(p: Promotion) -> dict:
    return {
        "id": str(p.id), "title": p.title, "promo_type": p.promo_type,
        "buy_qty": p.buy_qty, "get_qty": p.get_qty,
        "discount_percent": p.discount_percent, "discount_cents": p.discount_cents,
        "min_order_cents": p.min_order_cents, "applies_to_group": p.applies_to_group,
        "schedule": p.schedule or {}, "is_active": p.is_active,
    }


@router.get("/promotions")
async def list_promotions(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Promotion).where(Promotion.tenant_id == user.tenant_id).order_by(Promotion.created_at.desc()))
    return [_promotion_dict(p) for p in result.scalars().all()]


@router.post("/promotions")
async def create_promotion(body: PromotionBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    if body.promo_type not in ("buy_x_get_y", "percent_discount", "fixed_discount"):
        raise HTTPException(status_code=400, detail="Tipo di promozione non valido")
    promo = Promotion(tenant_id=user.tenant_id, **body.model_dump())
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    await _sync_agent(db, tenant)
    return _promotion_dict(promo)


@router.put("/promotions/{promotion_id}")
async def update_promotion(promotion_id: uuid.UUID, body: PromotionBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    if body.promo_type not in ("buy_x_get_y", "percent_discount", "fixed_discount"):
        raise HTTPException(status_code=400, detail="Tipo di promozione non valido")
    promo = await db.get(Promotion, promotion_id)
    if not promo or promo.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Promozione non trovata")
    for field, value in body.model_dump().items():
        setattr(promo, field, value)
    await db.commit()
    await _sync_agent(db, tenant)
    return _promotion_dict(promo)


@router.delete("/promotions/{promotion_id}")
async def delete_promotion(promotion_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    promo = await db.get(Promotion, promotion_id)
    if not promo or promo.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Promozione non trovata")
    await db.delete(promo)
    await db.commit()
    await _sync_agent(db, tenant)
    return {"ok": True}


class ResourceBody(BaseModel):
    resource_type: str = "table"
    name: str
    capacity: int | None = None
    is_active: bool = True


@router.get("/resources")
async def list_resources(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BookableResource).where(BookableResource.tenant_id == user.tenant_id))
    return [
        {"id": str(r.id), "resource_type": r.resource_type, "name": r.name, "capacity": r.capacity, "is_active": r.is_active}
        for r in result.scalars().all()
    ]


@router.post("/resources")
async def create_resource(body: ResourceBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    resource = BookableResource(tenant_id=user.tenant_id, **body.model_dump())
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return {"id": str(resource.id), "resource_type": resource.resource_type, "name": resource.name, "capacity": resource.capacity}


@router.delete("/resources/{resource_id}")
async def delete_resource(resource_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    resource = await db.get(BookableResource, resource_id)
    if not resource or resource.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Risorsa non trovata")
    await db.delete(resource)
    await db.commit()
    return {"ok": True}


@router.get("/kyc-documents")
async def list_kyc_documents(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    docs = (await db.execute(select(KycDocument).where(KycDocument.tenant_id == user.tenant_id))).scalars().all()
    return [{"id": str(d.id), "doc_type": d.doc_type, "file_url": d.file_url} for d in docs]


@router.post("/kyc-documents")
async def upload_kyc_document(doc_type: str, file: UploadFile, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
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
async def submit_for_review(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
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


# Numero di telefono self-service: stesso flusso DIDWW gia' usato dal
# pannello admin (app/routers/admin.py), ma qui scelto dal titolare stesso
# per il proprio tenant - la ricerca e' sempre filtrata sulla zona del suo
# indirizzo (vedi didww_geo.find_numbers_for_tenant), mai su citta' scollegate.
# L'ordine finale su DIDWW non e' istantaneo (verifica regolatoria + tempi di
# evasione loro): il numero vero e proprio viene collegato al tenant da un
# admin quando DIDWW conferma, stesso punto gia' vero per il flusso admin.
async def _get_or_create_didww_profile(db: AsyncSession, tenant_id: uuid.UUID) -> DidwwRegulatoryProfile:
    profile = (await db.execute(select(DidwwRegulatoryProfile).where(DidwwRegulatoryProfile.tenant_id == tenant_id))).scalar_one_or_none()
    if not profile:
        profile = DidwwRegulatoryProfile(tenant_id=tenant_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/didww/search")
async def didww_search(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    if not tenant.city:
        raise HTTPException(status_code=400, detail="Completa prima città e indirizzo nei dati attività")
    try:
        result = await didww_geo.find_numbers_for_tenant(tenant.city, tenant.province)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ricerca numeri fallita: {e}")
    return result


class DidwwReserveBody(BaseModel):
    available_did_id: str
    sku_id: str
    number: str


@router.post("/didww/reserve")
async def didww_reserve(body: DidwwReserveBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_didww_profile(db, user.tenant_id)
    try:
        reservation = await didww_client.reserve_did(body.available_did_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Prenotazione numero fallita: {e}")
    profile.available_did_id = body.available_did_id
    profile.did_reservation_id = reservation["id"]
    profile.sku_id = body.sku_id
    profile.phone_number = body.number
    await db.commit()
    return {"ok": True, "expires_at": reservation.get("attributes", {}).get("expires_at")}


class DidwwIdentityBody(BaseModel):
    identity_type: str = "business"
    first_name: str
    last_name: str
    contact_email: str
    phone_number: str
    company_name: str | None = None
    company_reg_number: str | None = None


@router.post("/didww/identity")
async def didww_identity(body: DidwwIdentityBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_didww_profile(db, user.tenant_id)
    try:
        identity_id = await didww_client.create_identity(**body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Creazione identità fallita: {e}")
    profile.identity_id = identity_id
    await db.commit()
    return {"ok": True}


class DidwwAddressBody(BaseModel):
    postal_code: str


@router.post("/didww/address")
async def didww_address(body: DidwwAddressBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await _require_tenant(db, user)
    profile = await _get_or_create_didww_profile(db, user.tenant_id)
    if not profile.identity_id:
        raise HTTPException(status_code=400, detail="Crea prima l'identità")
    if not tenant.address or not tenant.city:
        raise HTTPException(status_code=400, detail="Indirizzo attività incompleto - completalo nei dati attività prima di procedere")

    country_id = await didww_geo._italy_country_id()
    if not country_id:
        raise HTTPException(status_code=502, detail="Lookup paese DIDWW fallito")
    try:
        address_id = await didww_client.create_address(
            identity_id=profile.identity_id, country_id=country_id,
            city_name=tenant.city, postal_code=body.postal_code, address=tenant.address,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Creazione indirizzo fallita: {e}")
    profile.address_id = address_id
    await db.commit()
    return {"ok": True}


class DidwwUploadDocBody(BaseModel):
    kyc_document_id: uuid.UUID


@router.post("/didww/upload-document")
async def didww_upload_document(body: DidwwUploadDocBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    doc = await db.get(KycDocument, body.kyc_document_id)
    if not doc or doc.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    filename = doc.file_url.rsplit("/", 1)[-1]
    disk_path = os.path.join(UPLOADS_DIR, str(user.tenant_id), filename)
    if not os.path.isfile(disk_path):
        raise HTTPException(status_code=404, detail="File non trovato su disco")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "application/octet-stream")

    with open(disk_path, "rb") as f:
        file_bytes = f.read()

    try:
        encrypted_file_id = await didww_client.upload_encrypted_file(file_bytes, filename, content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Caricamento documento fallito: {e}")

    profile = await _get_or_create_didww_profile(db, user.tenant_id)
    profile.encrypted_file_ids = list(profile.encrypted_file_ids or []) + [encrypted_file_id]
    await db.commit()
    return {"ok": True}


@router.post("/didww/order")
async def didww_order(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_didww_profile(db, user.tenant_id)
    if not profile.encrypted_file_ids:
        raise HTTPException(status_code=400, detail="Carica almeno un documento prima di ordinare il numero")
    if not (profile.did_reservation_id and profile.sku_id):
        raise HTTPException(status_code=400, detail="Manca la prenotazione del numero")
    try:
        order = await didww_client.create_order(did_reservation_id=profile.did_reservation_id, sku_id=profile.sku_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ordine fallito: {e}")
    profile.order_id = order["id"]
    profile.order_status = order.get("attributes", {}).get("status")
    await db.commit()
    return {"ok": True, "order_id": profile.order_id, "order_status": profile.order_status}


@router.post("/didww/verify")
async def didww_verify(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_didww_profile(db, user.tenant_id)
    if not (profile.order_id and profile.address_id and profile.encrypted_file_ids):
        raise HTTPException(status_code=400, detail="Serve prima l'ordine, l'indirizzo e almeno un documento")

    if not profile.did_id:
        did = None
        try:
            did = await didww_client.find_did_by_number(profile.phone_number)
        except Exception as e:
            sys.stderr.write(f"Lookup DID fallito per tenant {user.tenant_id}: {e}\n")
        if not did:
            raise HTTPException(status_code=409, detail="Il numero non è ancora pronto lato DIDWW - riprova tra qualche minuto")
        profile.did_id = did["id"]
        await db.commit()

    try:
        verification = await didww_client.create_address_verification(
            did_id=profile.did_id, address_id=profile.address_id,
            encrypted_file_ids=profile.encrypted_file_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Avvio verifica fallito: {e}")
    profile.verification_id = verification["id"]
    profile.verification_status = verification.get("attributes", {}).get("status")
    await db.commit()
    return {"ok": True, "status": profile.verification_status}


@router.get("/didww/status")
async def didww_status(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(DidwwRegulatoryProfile).where(DidwwRegulatoryProfile.tenant_id == user.tenant_id))).scalar_one_or_none()
    if not profile:
        return {"exists": False}

    await refresh_did_activation(db, profile)

    return {
        "exists": True, "available_did_id": profile.available_did_id,
        "phone_number": profile.phone_number,
        "identity_id": profile.identity_id, "address_id": profile.address_id,
        "documents_uploaded": len(profile.encrypted_file_ids or []),
        "order_id": profile.order_id, "order_status": profile.order_status,
        "verification_id": profile.verification_id,
        "verification_status": profile.verification_status,
        "verification_reject_reason": profile.verification_reject_reason,
        "activation_status": profile.activation_status,
    }
