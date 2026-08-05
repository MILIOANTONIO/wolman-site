"""
Endpoint richiamato da ElevenLabs come "server tool" a metà chiamata (non a
fine chiamata come il webhook post_call_transcription): cosi' l'ordine
compare in dashboard mentre il cliente è ancora al telefono.
"""
import sys
import uuid

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ELEVENLABS_WEBHOOK_SECRET
from app.db import get_db
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
        )
    except OrderError as e:
        sys.stderr.write(f"record_reservation error per tenant {body.tenant_id}: {e}\n")
        raise HTTPException(status_code=400, detail=str(e))

    return {"reservation_id": str(reservation.id), "starts_at": reservation.starts_at.isoformat()}


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
        )
    except OrderError as e:
        sys.stderr.write(f"record_order error per tenant {body.tenant_id}: {e}\n")
        raise HTTPException(status_code=400, detail=str(e))

    return {"order_id": str(order.id), "order_number": order.order_number, "total_cents": order.total_cents}
