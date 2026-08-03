"""
Creazione/aggiornamento dell'agente vocale ElevenLabs per un tenant, via
Agents API (non usata finora nel repo: finora ogni agente era configurato a
mano nella dashboard). L'agent_id restituito va salvato su tenant.elevenlabs_agent_id.

NOTA: la forma esatta del payload va riverificata contro la documentazione
ElevenLabs corrente al primo utilizzo reale (l'API conversazionale evolve) -
qui logghiamo sempre il corpo della risposta in caso di errore, come già
fatto per Resend in wolman-site/server/chat_server.py, cosi' un eventuale
scostamento si vede subito nei log invece di fallire in silenzio.
"""
import re
import sys

import httpx

from app.config import ELEVENLABS_API_KEY
from app.services.claude_client import call_claude_with_tools

BASE_URL = "https://api.elevenlabs.io/v1/convai/agents"


def _headers():
    return {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}


def _agent_payload(*, name: str, prompt: str, first_message: str, voice_id: str | None, language: str = "it"):
    tts = {"voice_id": voice_id} if voice_id else {}
    return {
        "name": name,
        "conversation_config": {
            "agent": {
                "prompt": {"prompt": prompt},
                "first_message": first_message,
                "language": language,
            },
            "tts": tts,
        },
    }


async def create_agent(*, name: str, prompt: str, first_message: str, voice_id: str | None) -> str:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    payload = _agent_payload(name=name, prompt=prompt, first_message=first_message, voice_id=voice_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BASE_URL}/create", json=payload, headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs create_agent error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        data = resp.json()
        return data["agent_id"]


async def update_agent(agent_id: str, *, name: str, prompt: str, first_message: str, voice_id: str | None) -> None:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    payload = _agent_payload(name=name, prompt=prompt, first_message=first_message, voice_id=voice_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(f"{BASE_URL}/{agent_id}", json=payload, headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs update_agent error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()


PITCH_LINE = "Ciao, sono il tuo nuovo agente AI. Se la mia voce ti piace, scegli me!"


async def generate_voice_preview(voice_id: str, text: str = PITCH_LINE) -> bytes:
    """Genera al volo un audio di anteprima con una frase scelta da noi (non il preview_url generico di ElevenLabs) - richiede il permesso 'Text to Speech' sulla API key."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    payload = {"text": text, "model_id": "eleven_multilingual_v2"}
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", json=payload, headers=headers)
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs generate_voice_preview error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        return resp.content


# Le voci della libreria ElevenLabs hanno nomi tipo "Roger - Laid-Back,
# Casual, Resonant": traduciamo solo la parte descrittiva dopo il trattino,
# con una cache in memoria di processo cosi' non si ritraduce ad ogni
# caricamento della pagina (si perde solo al riavvio del server).
_NAME_PATTERN = re.compile(r"^(.+?) - (.+)$")
_descriptor_translation_cache: dict[str, str] = {}

_TRANSLATE_TOOL = {
    "name": "translate_descriptors",
    "description": "Registra la traduzione italiana di ciascun descrittore vocale.",
    "input_schema": {
        "type": "object",
        "properties": {
            "translations": {
                "type": "object",
                "description": "mappa testo originale in inglese -> traduzione italiana",
                "additionalProperties": {"type": "string"},
            }
        },
        "required": ["translations"],
    },
}


async def _translate_descriptors(descriptors: list[str]) -> dict[str, str]:
    uncached = sorted({d for d in descriptors if d not in _descriptor_translation_cache})
    if not uncached:
        return _descriptor_translation_cache

    system_prompt = (
        "Traduci in italiano queste brevi descrizioni di timbri vocali (una per riga). "
        "Mantieni lo stile: aggettivi/sostantivi brevi separati da virgola, senza tradurre nomi propri. "
        "Usa lo strumento translate_descriptors con chiave = testo originale esatto, valore = traduzione italiana."
    )
    try:
        response = await call_claude_with_tools(system_prompt, [{"role": "user", "content": "\n".join(uncached)}], tools=[_TRANSLATE_TOOL])
        content_blocks = response.get("content", [])
        tool_use = next((b for b in content_blocks if b.get("type") == "tool_use" and b.get("name") == "translate_descriptors"), None)
        if tool_use:
            _descriptor_translation_cache.update(tool_use.get("input", {}).get("translations", {}))
    except Exception as e:
        sys.stderr.write(f"Traduzione descrittori voce fallita: {e}\n")
    return _descriptor_translation_cache


async def list_voices() -> list[dict]:
    """Usato dal wizard di onboarding per far scegliere la voce al cliente."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://api.elevenlabs.io/v1/voices", headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs list_voices error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        data = resp.json()

    voices_raw = data.get("voices", [])
    parsed = []
    descriptors = []
    for v in voices_raw:
        m = _NAME_PATTERN.match(v["name"])
        if m:
            parsed.append((v, m.group(1), m.group(2)))
            descriptors.append(m.group(2))
        else:
            parsed.append((v, v["name"], None))

    translations = await _translate_descriptors(descriptors) if descriptors else {}

    result = []
    for v, base_name, descriptor in parsed:
        display_name = f"{base_name} - {translations.get(descriptor, descriptor)}" if descriptor else base_name
        result.append({"voice_id": v["voice_id"], "name": display_name, "preview_url": v.get("preview_url")})
    return result
