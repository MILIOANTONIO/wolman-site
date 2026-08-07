"""
Pagina pubblica del locale (nessuna autenticazione): usata dal frontend per
la landing page /site/{slug}. Espone solo dati pensati per essere pubblici -
mai email, credenziali, documenti KYC, dati di fatturazione. Il numero di
telefono è incluso perché è comunque il numero pubblico da chiamare.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db import get_db
from app.models import MediaPhoto, Offering, PhoneNumber, Tenant, TenantSettings

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/{slug}")
async def get_public_tenant(slug: str, db: AsyncSession = Depends(get_db)):
    tenant = (await db.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
    # Niente 404 con dettaglio diverso per "non esiste" vs "non ancora attivo":
    # evita di far capire dall'esterno se uno slug e' semplicemente non
    # attivato, in fase di revisione, sospeso, ecc.
    if not tenant or tenant.status != "active":
        raise HTTPException(status_code=404, detail="Pagina non trovata")

    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    offerings = (
        await db.execute(select(Offering).where(Offering.tenant_id == tenant.id, Offering.is_available.is_(True)).order_by(Offering.group_name, Offering.name))
    ).scalars().all()
    photos = (
        await db.execute(select(MediaPhoto).where(MediaPhoto.tenant_id == tenant.id).order_by(MediaPhoto.position, MediaPhoto.created_at))
    ).scalars().all()
    phone = (await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant.id, PhoneNumber.status == "active"))).scalars().first()

    return {
        "business_name": tenant.business_name,
        "category": tenant.category,
        "address": tenant.address,
        "city": tenant.city,
        "province": tenant.province,
        "logo_url": tenant.logo_url,
        "phone_number": phone.e164_number if phone else None,
        "elevenlabs_agent_id": tenant.elevenlabs_agent_id,
        "widget_avatar_url": settings_row.widget_avatar_url,
        "widget_color_1": settings_row.widget_color_1,
        "widget_color_2": settings_row.widget_color_2,
        "widget_action_text": settings_row.widget_action_text,
        "widget_variant": settings_row.widget_variant,
        "widget_placement": settings_row.widget_placement,
        "widget_dismissible": settings_row.widget_dismissible,
        "public_page_template": settings_row.public_page_template,
        "public_page_headline": settings_row.public_page_headline,
        "public_page_tagline": settings_row.public_page_tagline,
        "business_hours": settings_row.business_hours or {},
        "delivery_enabled": settings_row.delivery_enabled,
        "pickup_enabled": settings_row.pickup_enabled,
        "table_reservations_enabled": settings_row.table_reservations_enabled,
        "offerings": [
            {
                "name": o.name, "description": o.description, "price_cents": o.price_cents,
                "unit": o.unit, "group_name": o.group_name, "ingredients": o.ingredients,
            }
            for o in offerings
        ],
        "photos": [{"url": p.url, "caption": p.caption} for p in photos],
    }
