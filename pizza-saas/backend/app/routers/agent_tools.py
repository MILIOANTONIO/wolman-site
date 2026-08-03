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
from app.services.orders import OrderError, resolve_and_create_order

router = APIRouter(prefix="/api/agent-tools", tags=["agent-tools"])


class OrderItemIn(BaseModel):
    name: str
    quantity: int = 1
    notes: str | None = None


class RecordOrderBody(BaseModel):
    order_type: str  # delivery, pickup
    customer_name: str | None = None
    customer_phone: str | None = None
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
        )
    except OrderError as e:
        sys.stderr.write(f"record_order error per tenant {tenant_id}: {e}\n")
        # 400 con messaggio chiaro: l'agente vocale lo puo' leggere al
        # cliente ("non trovo questo piatto in menu") invece di fallire muto.
        raise HTTPException(status_code=400, detail=str(e))

    return {"order_id": str(order.id), "order_number": order.order_number, "total_cents": order.total_cents}
