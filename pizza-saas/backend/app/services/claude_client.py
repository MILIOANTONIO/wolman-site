"""
Chiamata alla Claude Messages API con tool use, per l'agente WhatsApp
testuale. Stesso endpoint/versione già usati in
wolman-site/server/chat_server.py, qui con supporto tool-use in più.
"""
import httpx

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_URL, ANTHROPIC_VERSION

RECORD_ORDER_TOOL = {
    "name": "record_order",
    "description": "Registra un ordine completo del cliente non appena hai raccolto tutte le informazioni necessarie.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_type": {"type": "string", "enum": ["delivery", "pickup"]},
            "customer_name": {"type": "string"},
            "delivery_address": {"type": "string", "description": "Indirizzo completo di consegna, richiesto solo se order_type è 'delivery'"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Nome esatto del piatto come in menu"},
                        "quantity": {"type": "integer"},
                        "notes": {"type": "string", "description": "Personalizzazioni richieste dal cliente per QUESTO piatto, es. 'senza cipolla', 'aggiungi funghi', 'doppia mozzarella', 'poco piccante'. Lascia vuoto se il cliente non ha chiesto modifiche."},
                    },
                    "required": ["name", "quantity"],
                },
            },
        },
        "required": ["order_type", "customer_name", "items"],
    },
}

RECORD_RESERVATION_TOOL = {
    "name": "record_reservation",
    "description": "Registra una prenotazione di un tavolo non appena hai raccolto tutte le informazioni necessarie (nome, numero di persone, data e ora).",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "description": "Nome e cognome del cliente"},
            "party_size": {"type": "integer", "description": "Numero di persone"},
            "date": {"type": "string", "description": "Data della prenotazione in formato AAAA-MM-GG"},
            "time": {"type": "string", "description": "Ora della prenotazione in formato HH:MM (24 ore)"},
            "notes": {"type": "string", "description": "Eventuali richieste particolari"},
        },
        "required": ["customer_name", "party_size", "date", "time"],
    },
}


async def call_claude_with_tools(system_prompt: str, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024) -> dict:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY non configurata sul server")

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("stop_reason") == "max_tokens":
            # La risposta (incluso il tool_use JSON) e' stata troncata a
            # meta': meglio segnalarlo chiaramente che restituire un
            # risultato vuoto/incompleto senza spiegazione.
            import sys
            sys.stderr.write("Claude ha troncato la risposta per max_tokens - considera di alzare il limite per questa chiamata\n")
        return data
