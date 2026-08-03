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
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Nome esatto del piatto come in menu"},
                        "quantity": {"type": "integer"},
                        "notes": {"type": "string"},
                    },
                    "required": ["name", "quantity"],
                },
            },
        },
        "required": ["order_type", "customer_name", "items"],
    },
}


async def call_claude_with_tools(system_prompt: str, messages: list[dict], tools: list[dict] | None = None) -> dict:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY non configurata sul server")

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
