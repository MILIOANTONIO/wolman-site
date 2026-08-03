"""
Canale ordini via WhatsApp: ElevenLabs è solo vocale/telefonico, quindi qui
costruiamo un handler testuale a parte che usa Claude con tool-use, ma
condivide lo stesso prompt (prompt_builder) e la stessa pipeline ordini
(orders.resolve_and_create_order) del canale voce.
"""
import hashlib
import hmac
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN
from app.db import SessionLocal, get_db
from app.models import Tenant, WhatsappChannel, WhatsappConversation
from app.services.claude_client import RECORD_ORDER_TOOL, call_claude_with_tools
from app.services.crypto import decrypt_token
from app.services.orders import OrderError, resolve_and_create_order
from app.services.prompt_builder import build_agent_prompt
from app.services.whatsapp_client import send_text_message

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

MAX_HISTORY_MESSAGES = 20


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    if hub_mode == "subscribe" and WHATSAPP_VERIFY_TOKEN and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    raise HTTPException(status_code=403, detail="Verifica fallita")


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not WHATSAPP_APP_SECRET or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(WHATSAPP_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


@router.post("/webhook")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(raw_body, signature):
        sys.stderr.write("WhatsApp webhook: firma non valida\n")
        return {"ok": False}  # 200 comunque: Meta ritenta se risponde errore

    try:
        payload = await request.json()
        await _process_payload(payload)
    except Exception:
        sys.stderr.write("Errore elaborazione webhook WhatsApp\n")

    return {"ok": True}


async def _process_payload(payload: dict):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {}) or {}
            phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
            for message in value.get("messages", []) or []:
                if message.get("type") != "text":
                    continue  # MVP: solo messaggi testuali
                customer_phone = message["from"]
                text = message["text"]["body"]
                async with SessionLocal() as db:
                    await _handle_message(db, phone_number_id, customer_phone, text)


async def _handle_message(db: AsyncSession, phone_number_id: str, customer_phone: str, text: str):
    channel = (await db.execute(select(WhatsappChannel).where(WhatsappChannel.phone_number_id == phone_number_id))).scalar_one_or_none()
    if not channel:
        sys.stderr.write(f"Nessun tenant collegato al numero WhatsApp {phone_number_id}\n")
        return

    tenant = await db.get(Tenant, channel.tenant_id)
    if not tenant or tenant.status != "active":
        return

    conv = (await db.execute(
        select(WhatsappConversation).where(
            WhatsappConversation.tenant_id == tenant.id,
            WhatsappConversation.customer_phone == customer_phone,
        )
    )).scalar_one_or_none()
    if not conv:
        conv = WhatsappConversation(tenant_id=tenant.id, customer_phone=customer_phone, history=[])
        db.add(conv)

    history = list(conv.history or [])
    history.append({"role": "user", "content": text})

    system_prompt = await build_agent_prompt(db, tenant, channel="whatsapp")
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in history[-MAX_HISTORY_MESSAGES:]]

    response = await call_claude_with_tools(system_prompt, claude_messages, tools=[RECORD_ORDER_TOOL])
    content_blocks = response.get("content", [])

    tool_use = next((b for b in content_blocks if b.get("type") == "tool_use" and b.get("name") == "record_order"), None)
    reply_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

    access_token = decrypt_token(channel.access_token_encrypted)

    if tool_use:
        args = tool_use.get("input", {})
        try:
            order = await resolve_and_create_order(
                db,
                tenant_id=tenant.id,
                channel="whatsapp",
                order_type=args.get("order_type", "pickup"),
                customer_name=args.get("customer_name"),
                customer_phone=customer_phone,
                items_by_name=args.get("items", []),
            )
            reply_text = (
                f"{reply_text}\n\nOrdine confermato #{order.order_number}, totale {order.total_cents / 100:.2f} euro."
                if reply_text else
                f"Ordine confermato #{order.order_number}, totale {order.total_cents / 100:.2f} euro. Grazie!"
            )
        except OrderError as e:
            reply_text = f"Non riesco a completare l'ordine: {e}. Puoi controllare il menu?"

    if not reply_text:
        reply_text = "Come posso aiutarti?"

    history.append({"role": "assistant", "content": reply_text})
    conv.history = history[-MAX_HISTORY_MESSAGES:]
    await db.commit()

    await send_text_message(phone_number_id, access_token, customer_phone, reply_text)
