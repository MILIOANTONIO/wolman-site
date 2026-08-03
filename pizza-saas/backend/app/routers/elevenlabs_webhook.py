"""
Webhook post_call_transcription di ElevenLabs: arriva a chiamata conclusa,
quando l'ordine (se c'è stato) è già stato registrato dal tool a metà
chiamata (vedi agent_tools.py) - qui NON creiamo un altro ordine, altrimenti
lo duplichiamo. Logga il riepilogo e registra i minuti di chiamata per la
fatturazione prepagata (billing.record_call_minutes). Stesso pattern di
verifica firma e risposta-sempre-200 già collaudato in
unitel-1mobile/server/webhook_server.py.
"""
import math
import sys

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from app.config import ELEVENLABS_WEBHOOK_SECRET
from app.db import SessionLocal
from app.models import Tenant
from app.services import billing

router = APIRouter(prefix="/api/elevenlabs-webhook", tags=["voice"])


@router.post("")
async def elevenlabs_webhook(request: Request, elevenlabs_signature: str | None = Header(default=None)):
    raw_body = await request.body()
    try:
        result = await _handle(raw_body, elevenlabs_signature)
        sys.stderr.write(f"ElevenLabs webhook handled: {result}\n")
    except Exception as e:
        sys.stderr.write(f"Webhook error: {e}\n")
    # Rispondiamo comunque 200: un errore farebbe ritentare ElevenLabs più volte.
    return {"ok": True}


async def _handle(raw_body: bytes, signature_header: str | None) -> dict:
    from elevenlabs import ElevenLabs  # import locale: dipendenza usata solo qui

    if not ELEVENLABS_WEBHOOK_SECRET:
        raise RuntimeError("ELEVENLABS_WEBHOOK_SECRET non configurata sul server")
    if not signature_header:
        raise RuntimeError("Firma mancante")

    client = ElevenLabs()
    event = client.webhooks.construct_event(raw_body.decode("utf-8"), signature_header, ELEVENLABS_WEBHOOK_SECRET)

    if event.get("type") != "post_call_transcription":
        return {"skipped": event.get("type")}

    data = event.get("data", {}) or {}
    analysis = data.get("analysis", {}) or {}
    metadata = data.get("metadata", {}) or {}
    summary = analysis.get("transcript_summary", "")
    sys.stderr.write(f"Riepilogo chiamata: {summary}\n")

    agent_id = data.get("agent_id") or metadata.get("agent_id")
    duration_secs = metadata.get("call_duration_secs")

    if not agent_id or duration_secs is None:
        sys.stderr.write(f"Webhook senza agent_id/durata utilizzabili: chiavi metadata={list(metadata.keys())}\n")
        return {"logged": True, "billed": False}

    async with SessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.elevenlabs_agent_id == agent_id))).scalar_one_or_none()
        if not tenant:
            sys.stderr.write(f"Nessun tenant trovato per agent_id {agent_id}\n")
            return {"logged": True, "billed": False}

        minutes = math.ceil(duration_secs / 60)  # come da prassi telefonia, minuto parziale arrotondato per eccesso
        await billing.record_call_minutes(db, tenant, minutes)

    return {"logged": True, "billed": True, "minutes": minutes}
