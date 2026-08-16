"""
Pagina pubblica del locale (nessuna autenticazione): usata dal frontend per
la landing page /site/{slug}. Espone solo dati pensati per essere pubblici -
mai email, credenziali, documenti KYC, dati di fatturazione. Il numero di
telefono è incluso perché è comunque il numero pubblico da chiamare.

Il contenuto del tenant (piatti, headline, tagline, categoria) e' tradotto
in scrittura - vedi onboarding.py - e salvato in offering_translations /
tenant_translations: questo endpoint legge solo, non chiama mai DeepL.
L'endpoint /translate resta per le sole stringhe fisse del template
(Menu, Orari, Foto...), tradotte al volo dal frontend con cache condivisa.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import MediaPhoto, Offering, OfferingTranslation, PhoneNumber, Promotion, Tenant, TenantSettings, TenantTranslation
from app.services.translation import MAX_TEXTS_PER_REQUEST, SUPPORTED_LANGS, translate_batch

# Frasi fisse (non il titolo, quello e' testo libero del tenant) per descrivere il tipo di promo
# sulla pagina pubblica - tradotte al volo come le altre stringhe fisse del template, dato che
# sono poche parole e cambiano raramente (niente storage dedicato per un caso cosi' piccolo).
_PROMO_PHRASES = {
    "it": {"buy_x_get_y": "Paghi {buy}, prendi {get}", "percent_discount": "{pct}% di sconto", "fixed_discount": "{amount} di sconto", "min_order": "sopra i {amount}"},
    "en": {"buy_x_get_y": "Buy {buy}, get {get}", "percent_discount": "{pct}% off", "fixed_discount": "{amount} off", "min_order": "over {amount}"},
    "fr": {"buy_x_get_y": "Achetez {buy}, recevez {get}", "percent_discount": "{pct}% de réduction", "fixed_discount": "{amount} de réduction", "min_order": "au-dessus de {amount}"},
    "de": {"buy_x_get_y": "{buy} kaufen, {get} erhalten", "percent_discount": "{pct}% Rabatt", "fixed_discount": "{amount} Rabatt", "min_order": "ab {amount}"},
    "es": {"buy_x_get_y": "Compra {buy}, llévate {get}", "percent_discount": "{pct}% de descuento", "fixed_discount": "{amount} de descuento", "min_order": "a partir de {amount}"},
}


def _format_promo_description(p: Promotion, lang: str) -> str:
    phrases = _PROMO_PHRASES.get(lang, _PROMO_PHRASES["it"])
    if p.promo_type == "buy_x_get_y" and p.buy_qty and p.get_qty:
        line = phrases["buy_x_get_y"].format(buy=p.buy_qty, get=p.get_qty)
    elif p.promo_type == "percent_discount" and p.discount_percent:
        line = phrases["percent_discount"].format(pct=int(p.discount_percent) if p.discount_percent == int(p.discount_percent) else p.discount_percent)
    elif p.promo_type == "fixed_discount" and p.discount_cents:
        line = phrases["fixed_discount"].format(amount=f"{p.discount_cents / 100:.2f} €")
    else:
        line = ""
    if p.min_order_cents:
        line = f"{line} {phrases['min_order'].format(amount=f'{p.min_order_cents / 100:.2f} €')}".strip()
    return line

router = APIRouter(prefix="/api/public", tags=["public"])


class TranslateRequest(BaseModel):
    texts: list[str] = Field(..., max_length=MAX_TEXTS_PER_REQUEST)
    target_lang: str


@router.post("/translate")
async def translate_public_texts(payload: TranslateRequest, db: AsyncSession = Depends(get_db)):
    try:
        translations = await translate_batch(db, payload.texts, payload.target_lang)
    except ValueError:
        raise HTTPException(status_code=400, detail="Lingua non supportata")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"translations": translations}


@router.get("/{slug}")
async def get_public_tenant(slug: str, lang: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    tenant = (await db.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
    # Niente 404 con dettaglio diverso per "non esiste" vs "non ancora attivo":
    # evita di far capire dall'esterno se uno slug e' semplicemente non
    # attivato, in fase di revisione, sospeso, ecc.
    if not tenant or tenant.status != "active":
        raise HTTPException(status_code=404, detail="Pagina non trovata")

    lang = (lang or "it").lower()
    if lang not in SUPPORTED_LANGS:
        lang = "it"

    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    offerings = (
        await db.execute(select(Offering).where(Offering.tenant_id == tenant.id, Offering.is_available.is_(True)).order_by(Offering.group_name, Offering.name))
    ).scalars().all()
    photos = (
        await db.execute(select(MediaPhoto).where(MediaPhoto.tenant_id == tenant.id).order_by(MediaPhoto.position, MediaPhoto.created_at))
    ).scalars().all()
    phone = (await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant.id, PhoneNumber.status == "active"))).scalars().first()
    promotions = (
        await db.execute(select(Promotion).where(Promotion.tenant_id == tenant.id, Promotion.is_active.is_(True)).order_by(Promotion.created_at))
    ).scalars().all()

    offering_tr: dict = {}
    tenant_tr: TenantTranslation | None = None
    if lang != "it":
        offering_ids = [o.id for o in offerings]
        if offering_ids:
            rows = (
                await db.execute(
                    select(OfferingTranslation).where(OfferingTranslation.offering_id.in_(offering_ids), OfferingTranslation.lang == lang)
                )
            ).scalars().all()
            offering_tr = {r.offering_id: r for r in rows}
        tenant_tr = (
            await db.execute(select(TenantTranslation).where(TenantTranslation.tenant_id == tenant.id, TenantTranslation.lang == lang))
        ).scalar_one_or_none()

    promo_titles = [p.title for p in promotions]
    if lang != "it" and promo_titles:
        try:
            promo_titles = await translate_batch(db, promo_titles, lang)
        except Exception:
            pass  # se DeepL non risponde mostriamo il titolo originale, meglio che rompere la pagina

    offerings_by_id = {str(o.id): o for o in offerings}

    def offering_dict(o: Offering) -> dict:
        tr = offering_tr.get(o.id)
        return {
            "name": (tr.name if tr else None) or o.name,
            "description": (tr.description if tr else None) or o.description,
            "price_cents": o.price_cents,
            "unit": o.unit,
            "group_name": (tr.group_name if tr else None) or o.group_name,
            "ingredients": (tr.ingredients if tr else None) or o.ingredients,
            "image_url": o.image_url,
            "is_featured": o.is_featured,
        }

    def promo_offerings(p: Promotion) -> list[dict]:
        # Piatti scelti dal titolare come protagonisti di questa promo (in ordine di scelta) - usati per
        # la vetrina della sezione promozione sulla pagina pubblica (mai i piatti "in evidenza" generici).
        return [offering_dict(offerings_by_id[str(oid)]) for oid in (p.offering_ids or []) if str(oid) in offerings_by_id]

    def promo_photos(p: Promotion) -> list[str]:
        return [o["image_url"] for o in promo_offerings(p) if o["image_url"]]

    return {
        "business_name": tenant.business_name,
        "category": (tenant_tr.category if tenant_tr else None) or tenant.category,
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
        "public_page_headline": (tenant_tr.headline if tenant_tr else None) or settings_row.public_page_headline,
        "public_page_tagline": (tenant_tr.tagline if tenant_tr else None) or settings_row.public_page_tagline,
        "business_hours": settings_row.business_hours or {},
        "delivery_enabled": settings_row.delivery_enabled,
        "pickup_enabled": settings_row.pickup_enabled,
        "table_reservations_enabled": settings_row.table_reservations_enabled,
        "offerings": [offering_dict(o) for o in offerings],
        "photos": [{"url": p.url, "caption": p.caption} for p in photos],
        "promotions": [
            {
                "title": title,
                "description": _format_promo_description(p, lang),
                "promo_type": p.promo_type,
                "discount_percent": p.discount_percent,
                "discount_cents": p.discount_cents,
                "buy_qty": p.buy_qty,
                "get_qty": p.get_qty,
                "photo_urls": promo_photos(p),
                "offerings": promo_offerings(p),
            }
            for p, title in zip(promotions, promo_titles)
        ],
    }
