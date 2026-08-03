"""
Invio messaggi WhatsApp (Meta Cloud API) e trigger delle notifiche di stato
ordine. Stesso pattern difensivo già collaudato per Resend: User-Agent
esplicito, log del corpo risposta su errore, non solleva mai un'eccezione
che possa bloccare l'aggiornamento di stato ordine sulla dashboard.
"""
import sys

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import WHATSAPP_GRAPH_URL
from app.models import Order, OrderStatusHistory, Tenant, WhatsappChannel
from app.services.crypto import decrypt_token
from app.services.whatsapp_templates import phrase_for_status


async def _post_message(phone_number_id: str, access_token: str, payload: dict):
    url = f"{WHATSAPP_GRAPH_URL}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "pizza-saas-backend/1.0",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            sys.stderr.write(f"WhatsApp API error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        return resp.json()


async def send_text_message(phone_number_id: str, access_token: str, to_number: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    return await _post_message(phone_number_id, access_token, payload)


async def send_status_template(phone_number_id: str, access_token: str, to_number: str, customer_name: str, business_name: str, status_phrase: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "order_status_update",
            "language": {"code": "it"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": customer_name or "cliente"},
                    {"type": "text", "text": business_name},
                    {"type": "text", "text": status_phrase},
                ],
            }],
        },
    }
    return await _post_message(phone_number_id, access_token, payload)


async def notify_order_status(db: AsyncSession, *, order: Order, history: OrderStatusHistory):
    if not order.customer_phone:
        return

    channel = (await db.execute(select(WhatsappChannel).where(WhatsappChannel.tenant_id == order.tenant_id))).scalar_one_or_none()
    if not channel or not channel.verified_at:
        return  # tenant senza WhatsApp collegato: nessuna notifica, nessun errore

    tenant = await db.get(Tenant, order.tenant_id)

    try:
        access_token = decrypt_token(channel.access_token_encrypted)
        await send_status_template(
            channel.phone_number_id,
            access_token,
            order.customer_phone,
            order.customer_name or "cliente",
            tenant.business_name,
            phrase_for_status(order.status),
        )
        history.notification_sent = True
        await db.commit()
    except Exception:
        # Non deve mai bloccare l'aggiornamento di stato dell'ordine:
        # logghiamo e andiamo avanti, notification_sent resta False.
        sys.stderr.write(f"Invio notifica WhatsApp fallito per ordine {order.id}\n")
