"""
Endpoint richiamato da ElevenLabs come "server tool" a metà chiamata (non a
fine chiamata come il webhook post_call_transcription): cosi' l'ordine
compare in dashboard mentre il cliente è ancora al telefono.
"""
import sys
import uuid

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ELEVENLABS_WEBHOOK_SECRET
from app.db import get_db
from app.models import Order, Reservation, Tenant, TenantSettings
from app.routers.ws import manager as ws_manager
from app.services.geocoding import geocode_address, haversine_km
from app.services.orders import OrderError, create_reservation, resolve_and_create_order

router = APIRouter(prefix="/api/agent-tools", tags=["agent-tools"])


class OrderItemIn(BaseModel):
    name: str
    quantity: int = 1
    notes: str | None = None


class RecordOrderBody(BaseModel):
    order_type: str  # delivery, pickup
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_address: str | None = None
    items: list[OrderItemIn]
    # ID di questa conversazione ElevenLabs (il prompt istruisce l'agente a
    # passare sempre {{system__conversation_id}}) - usato per far partire in
    # automatico la richiamata di conferma a fine chiamata.
    conversation_id: str | None = None


def _check_tool_secret(x_tool_secret: str | None):
    if not ELEVENLABS_WEBHOOK_SECRET or x_tool_secret != ELEVENLABS_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Non autorizzato")


@router.post("/{tenant_id}/record-order")
async def record_order(
    tenant_id: uuid.UUID,
    body: RecordOrderBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _check_tool_secret(x_tool_secret)
    try:
        order = await resolve_and_create_order(
            db,
            tenant_id=tenant_id,
            channel="voice",
            order_type=body.order_type,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            items_by_name=[item.model_dump() for item in body.items],
            delivery_address=body.delivery_address,
            conversation_id=body.conversation_id,
        )
    except OrderError as e:
        sys.stderr.write(f"record_order error per tenant {tenant_id}: {e}\n")
        # 400 con messaggio chiaro: l'agente vocale lo puo' leggere al
        # cliente ("non trovo questo piatto in menu") invece di fallire muto.
        raise HTTPException(status_code=400, detail=str(e))

    return {"order_id": str(order.id), "order_number": order.order_number, "total_cents": order.total_cents}


class RecordReservationBody(BaseModel):
    customer_name: str
    customer_phone: str | None = None
    party_size: int | None = None
    date: str
    time: str
    notes: str | None = None
    conversation_id: str | None = None


@router.post("/{tenant_id}/record-reservation")
async def record_reservation(
    tenant_id: uuid.UUID,
    body: RecordReservationBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _check_tool_secret(x_tool_secret)
    try:
        reservation = await create_reservation(
            db,
            tenant_id=tenant_id,
            channel="voice",
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            party_size=body.party_size,
            date=body.date,
            time=body.time,
            notes=body.notes,
            conversation_id=body.conversation_id,
        )
    except OrderError as e:
        sys.stderr.write(f"record_reservation error per tenant {tenant_id}: {e}\n")
        raise HTTPException(status_code=400, detail=str(e))

    return {"reservation_id": str(reservation.id), "starts_at": reservation.starts_at.isoformat()}


class RecordReservationGlobalBody(RecordReservationBody):
    # Il tool "record_reservation" e' configurato UNA VOLTA SOLA su
    # ElevenLabs e riusato da tutti gli agenti (vedi
    # ELEVENLABS_RESERVATION_TOOL_ID): l'URL e' quindi identico per ogni
    # tenant, e il tenant_id arriva nel body invece che nel path. Il valore
    # esatto e' scritto nel prompt di ogni agente, cosi' il modello lo passa
    # sempre correttamente senza doverlo indovinare.
    tenant_id: uuid.UUID


@router.post("/record-reservation")
async def record_reservation_global(
    body: RecordReservationGlobalBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _check_tool_secret(x_tool_secret)
    try:
        reservation = await create_reservation(
            db,
            tenant_id=body.tenant_id,
            channel="voice",
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            party_size=body.party_size,
            date=body.date,
            time=body.time,
            notes=body.notes,
            conversation_id=body.conversation_id,
        )
    except OrderError as e:
        sys.stderr.write(f"record_reservation error per tenant {body.tenant_id}: {e}\n")
        raise HTTPException(status_code=400, detail=str(e))

    return {"reservation_id": str(reservation.id), "starts_at": reservation.starts_at.isoformat()}


class CheckDeliveryDistanceBody(BaseModel):
    tenant_id: uuid.UUID
    address: str


@router.post("/check-delivery-distance")
async def check_delivery_distance(
    body: CheckDeliveryDistanceBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Tool globale (stesso schema di record_order/record_reservation): calcola
    la distanza reale tra l'indirizzo del locale e quello del cliente via
    geocoding Google, cosi' l'agente non deve indovinare se un indirizzo
    nella stessa citta' e' dentro o fuori dal raggio di consegna configurato."""
    _check_tool_secret(x_tool_secret)

    tenant = await db.get(Tenant, body.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Pizzeria non trovata")
    settings_row = (await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == body.tenant_id)
    )).scalar_one_or_none()
    radius_km = settings_row.delivery_radius_km if settings_row else None

    tenant_address = ", ".join(p for p in (tenant.address, tenant.city) if p)
    if not tenant_address:
        return {"distance_km": None, "in_zone": None, "reason": "Indirizzo del locale non configurato"}

    tenant_coords = await geocode_address(tenant_address, region_hint="it")
    customer_coords = await geocode_address(body.address, region_hint="it")
    if not tenant_coords or not customer_coords:
        return {"distance_km": None, "in_zone": None, "reason": "Indirizzo non riconosciuto, chiedi di ripeterlo con via e numero civico"}

    distance_km = round(haversine_km(*tenant_coords, *customer_coords), 1)
    in_zone = distance_km <= radius_km if radius_km is not None else None
    return {"distance_km": distance_km, "in_zone": in_zone, "radius_km": radius_km}


class RecordOrderGlobalBody(RecordOrderBody):
    # Stesso schema di RecordReservationGlobalBody: il tool "record_order" e'
    # configurato UNA VOLTA SOLA su ElevenLabs (ELEVENLABS_ORDER_TOOL_ID) e
    # riusato da tutti gli agenti, quindi il tenant_id arriva nel body invece
    # che nel path dell'URL.
    tenant_id: uuid.UUID


@router.post("/record-order")
async def record_order_global(
    body: RecordOrderGlobalBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _check_tool_secret(x_tool_secret)
    try:
        order = await resolve_and_create_order(
            db,
            tenant_id=body.tenant_id,
            channel="voice",
            order_type=body.order_type,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            items_by_name=[item.model_dump() for item in body.items],
            delivery_address=body.delivery_address,
            conversation_id=body.conversation_id,
        )
    except OrderError as e:
        sys.stderr.write(f"record_order error per tenant {body.tenant_id}: {e}\n")
        raise HTTPException(status_code=400, detail=str(e))

    return {"order_id": str(order.id), "order_number": order.order_number, "total_cents": order.total_cents}


class ConfirmOrderBody(BaseModel):
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    confirmed: bool


@router.post("/confirm-order")
async def confirm_order(
    body: ConfirmOrderBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Tool globale usato SOLO durante una richiamata di conferma (avviata da
    noi via place_outbound_call, mai da una chiamata in entrata normale)."""
    _check_tool_secret(x_tool_secret)
    order = await db.get(Order, body.order_id)
    if not order or order.tenant_id != body.tenant_id:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    order.confirmation_status = "confermato" if body.confirmed else "rifiutato"
    await db.commit()

    await ws_manager.broadcast(str(body.tenant_id), {
        "type": "order_confirmation_changed",
        "order_id": str(order.id),
        "confirmation_status": order.confirmation_status,
    })
    return {"ok": True}


class ConfirmReservationBody(BaseModel):
    tenant_id: uuid.UUID
    reservation_id: uuid.UUID
    confirmed: bool


@router.post("/confirm-reservation")
async def confirm_reservation(
    body: ConfirmReservationBody,
    x_tool_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _check_tool_secret(x_tool_secret)
    reservation = await db.get(Reservation, body.reservation_id)
    if not reservation or reservation.tenant_id != body.tenant_id:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    reservation.confirmation_status = "confermato" if body.confirmed else "rifiutato"
    await db.commit()

    await ws_manager.broadcast(str(body.tenant_id), {
        "type": "reservation_confirmation_changed",
        "reservation_id": str(reservation.id),
        "confirmation_status": reservation.confirmation_status,
    })
    return {"ok": True}
