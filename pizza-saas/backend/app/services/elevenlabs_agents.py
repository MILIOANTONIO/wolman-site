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

from app.config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_CONFIRM_ORDER_TOOL_ID,
    ELEVENLABS_CONFIRM_RESERVATION_TOOL_ID,
    ELEVENLABS_DISTANCE_TOOL_ID,
    ELEVENLABS_ORDER_TOOL_ID,
    ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID,
    ELEVENLABS_RESERVATION_TOOL_ID,
)
from app.services.claude_client import call_claude_with_tools

BASE_URL = "https://api.elevenlabs.io/v1/convai/agents"


def _headers():
    return {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}


def _agent_payload(*, name: str, prompt: str, first_message: str, voice_id: str | None, language: str = "it"):
    # ElevenLabs richiede il modello "turbo" o "flash v2_5" per gli agenti in
    # lingua non inglese (scoperto il 2026-08-05: la creazione falliva con
    # "Non-english Agents must use turbo or flash v2_5" senza model_id
    # esplicito) - flash v2_5 e' quello a latenza piu' bassa, adatto a una
    # telefonata dove ogni secondo di attesa si sente.
    tts: dict = {"model_id": "eleven_flash_v2_5"}
    if voice_id:
        tts["voice_id"] = voice_id
    prompt_config: dict = {"prompt": prompt}
    # "record_order" e "record_reservation" sono condivisi da tutti gli
    # agenti (creati una volta sola su ElevenLabs, vedi ELEVENLABS_ORDER_TOOL_ID
    # / ELEVENLABS_RESERVATION_TOOL_ID): collegarli qui evita di doverli
    # aggiungere a mano ad ogni pizzeria. Se il tenant non ha le prenotazioni
    # attive il prompt semplicemente non menziona record_reservation, quindi
    # l'agente non lo usa comunque anche se e' tecnicamente disponibile.
    tool_ids = [t for t in (
        ELEVENLABS_ORDER_TOOL_ID, ELEVENLABS_RESERVATION_TOOL_ID, ELEVENLABS_DISTANCE_TOOL_ID,
        ELEVENLABS_CONFIRM_ORDER_TOOL_ID, ELEVENLABS_CONFIRM_RESERVATION_TOOL_ID,
    ) if t]
    if tool_ids:
        prompt_config["tool_ids"] = tool_ids
    return {
        "name": name,
        "conversation_config": {
            "agent": {
                "prompt": prompt_config,
                "first_message": first_message,
                "language": language,
            },
            "tts": tts,
            # "eager" invece del default "normal": risponde/nota il silenzio
            # del cliente piu' rapidamente - richiesto dopo un test reale in
            # cui l'agente sembrava non accorgersi delle pause del cliente.
            "turn": {"turn_eagerness": "eager"},
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


# Numeri DIDWW -> ElevenLabs: stesso schema gia' funzionante sui numeri reali
# collegati a mano in precedenza (verificato leggendo /v1/convai/phone-numbers
# sull'account) - "allowed_addresses": ["0.0.0.0/0"] e nessuna credenziale,
# perche' DIDWW instrada le chiamate senza autenticazione SIP lato trunk in
# entrata. Niente outbound_trunk_config: questi numeri ricevono soltanto.
PHONE_NUMBERS_URL = "https://api.elevenlabs.io/v1/convai/phone-numbers"


async def import_phone_number(*, e164_number: str, label: str, agent_id: str | None = None) -> str:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    payload = {
        "phone_number": e164_number,
        "label": label,
        "provider": "sip_trunk",
        "agent_id": agent_id,
        "inbound_trunk_config": {"allowed_addresses": ["0.0.0.0/0"], "media_encryption": "allowed"},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(PHONE_NUMBERS_URL, json=payload, headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs import_phone_number error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        return resp.json()["phone_number_id"]


OUTBOUND_CALL_URL = "https://api.elevenlabs.io/v1/convai/sip-trunk/outbound-call"


def _to_e164_it(raw: str) -> str:
    """Il cliente detta il numero a voce e l'AI lo trascrive cosi' com'e'
    (es. "3773768606", senza prefisso) - una chiamata in uscita reale invece
    richiede il formato E.164 completo (+39...), altrimenti il trunk non sa
    instradarla correttamente. Assume Italia se non c'e' gia' un prefisso."""
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        return digits
    if digits.startswith("0039"):
        return "+" + digits[2:]
    if digits.startswith("39") and len(digits) >= 11:
        return "+" + digits
    if digits.startswith("0"):
        digits = digits[1:]
    return "+39" + digits


async def place_outbound_call(
    *, agent_id: str, to_number: str, first_message: str | None = None, dynamic_variables: dict | None = None
) -> dict:
    """Fa richiamare l'agente vocale al numero indicato (es. per avvisare di
    un ordine annullato, o per una richiamata di conferma) tramite il trunk
    DIDWW in uscita condiviso da tutti i tenant - vedi
    ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID in config.py. first_message e
    dynamic_variables permettono di dare all'agente il contesto specifico di
    QUESTA chiamata (es. quale ordine confermare) senza dover cambiare il
    prompt salvato sull'agente."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")
    if not ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID:
        raise RuntimeError("ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID non configurata sul server")

    payload: dict = {
        "agent_id": agent_id,
        "agent_phone_number_id": ELEVENLABS_OUTBOUND_PHONE_NUMBER_ID,
        "to_number": _to_e164_it(to_number),
    }
    client_data: dict = {}
    if first_message:
        client_data["conversation_config_override"] = {"agent": {"first_message": first_message}}
    if dynamic_variables:
        client_data["dynamic_variables"] = dynamic_variables
    if client_data:
        payload["conversation_initiation_client_data"] = client_data
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(OUTBOUND_CALL_URL, json=payload, headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs place_outbound_call error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        return resp.json()


CONVERSATIONS_URL = "https://api.elevenlabs.io/v1/convai/conversations"

# Traduzione dei motivi di fallimento SIP piu' comuni (DIDWW/ElevenLabs
# restituiscono un codice SIP dentro una frase tecnica in inglese, es.
# "unexpected status from INVITE response: sip status: 486: Busy Here") -
# il titolare deve capire cosa e' successo senza leggere gergo telefonico.
_SIP_ERROR_IT = {
    "400": "numero non valido",
    "403": "chiamata non autorizzata dal gestore telefonico",
    "404": "numero inesistente",
    "480": "cliente momentaneamente non raggiungibile",
    "486": "numero occupato",
    "487": "chiamata interrotta prima di rispondere",
    "488": "problema di compatibilità audio con il gestore telefonico",
    "500": "problema tecnico temporaneo della linea",
    "503": "servizio telefonico momentaneamente non disponibile",
    "603": "chiamata rifiutata",
}


def _translate_sip_error(raw_reason: str | None) -> str:
    if not raw_reason:
        return "errore tecnico durante la chiamata"
    match = re.search(r"\bsip status:\s*(\d{3})|\(SIP (\d{3})\)", raw_reason)
    code = next((g for g in (match.groups() if match else ()) if g), None)
    if code and code in _SIP_ERROR_IT:
        return _SIP_ERROR_IT[code]
    return "errore tecnico durante la chiamata"


async def get_outbound_call_status(conversation_id: str) -> dict:
    """Stato reale della chiamata su ElevenLabs - usato per capire se una
    richiamata di conferma e' fallita SUBITO (es. numero inesistente), prima
    ancora che arrivi il webhook post_call_transcription (che per una
    chiamata mai realmente connessa potrebbe non arrivare affatto)."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{CONVERSATIONS_URL}/{conversation_id}", headers=_headers())
        if resp.status_code >= 400:
            resp.raise_for_status()
        data = resp.json()

    status = data.get("status")
    error = (data.get("metadata") or {}).get("error") or {}
    return {
        # initiated -> squilla, in-progress -> risposta/in conversazione,
        # processing -> chiamata finita, elaborazione in corso, done -> finita
        "status": status,
        "status_it": _CALL_STATUS_IT.get(status, status),
        "failed": status == "failed",
        "done": status == "done",
        "error_reason_it": _translate_sip_error(error.get("reason")) if status == "failed" else None,
    }


_CALL_STATUS_IT = {
    "initiated": "📞 Squilla...",
    "in-progress": "🗣️ In conversazione...",
    "processing": "⏳ Chiamata terminata, elaborazione...",
    "done": "✅ Chiamata terminata",
    "failed": "❌ Chiamata fallita",
}


async def assign_phone_number(phone_number_id: str, agent_id: str | None) -> None:
    """agent_id=None sospende il numero (ElevenLabs smette di instradarlo a
    qualunque agente) senza doverlo re-importare - usato per la sospensione/
    riattivazione per mancato pagamento, vedi services/billing_enforcement.py."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(f"{PHONE_NUMBERS_URL}/{phone_number_id}", json={"agent_id": agent_id}, headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs assign_phone_number error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()


async def delete_phone_number(phone_number_id: str) -> None:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY non configurata sul server")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(f"{PHONE_NUMBERS_URL}/{phone_number_id}", headers=_headers())
        if resp.status_code >= 400:
            sys.stderr.write(f"ElevenLabs delete_phone_number error {resp.status_code}: {resp.text}\n")
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
