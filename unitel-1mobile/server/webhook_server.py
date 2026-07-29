"""
Unitel 1Mobile dealer agent: server minimale che riceve il webhook
post_call_transcription di ElevenLabs e manda un'email di riepilogo della
chiamata (riassunto + dati del dealer chiamante) via Resend.

Legge le variabili d'ambiente dal sistema, oppure da un file ".env.local"
nella stessa cartella dello script (mai committato su git).
"""
import json
import os
import sys
import traceback
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_local_env():
    path = os.path.join(SERVER_DIR, ".env.local")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and value and key not in os.environ:
                os.environ[key] = value


_load_local_env()


def _clean_env(name, default=None):
    # I pannelli web (Render, ecc.) a volte salvano un a-capo finale se il
    # valore incollato lo conteneva: eliminarlo evita errori "Invalid header
    # value" quando il valore finisce in un header HTTP.
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


RESEND_API_KEY = _clean_env("RESEND_API_KEY")
RESEND_URL = "https://api.resend.com/emails"
RESEND_FROM = _clean_env("RESEND_FROM", "Unitel 1Mobile <onboarding@resend.dev>")
ELEVENLABS_WEBHOOK_SECRET = _clean_env("ELEVENLABS_WEBHOOK_SECRET")
NOTIFY_EMAIL = _clean_env("UNITEL_NOTIFY_EMAIL")


def send_email(to_address, subject, text_body):
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY non configurata sul server")

    payload = json.dumps({
        "from": RESEND_FROM,
        "to": [to_address],
        "subject": subject,
        "text": text_body,
    }).encode("utf-8")

    req = urllib.request.Request(
        RESEND_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % RESEND_API_KEY,
            # Senza uno User-Agent "normale", Cloudflare (davanti a Resend)
            # blocca la richiesta come bot (errore 1010) prima che arrivi a Resend.
            "User-Agent": "unitel-1mobile-server/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        sys.stderr.write("Resend API error %s: %s\n" % (e.code, detail))
        raise


def _field(collected, *keys):
    for key in keys:
        entry = collected.get(key)
        if isinstance(entry, dict) and entry.get("value"):
            return entry["value"]
    return None


def _caller_number(data):
    # La posizione esatta del numero del chiamante nel payload non è
    # documentata in modo esplicito per post_call_transcription: proviamo i
    # percorsi più plausibili e logghiamo tutto se non troviamo nulla, cosi'
    # al primo test reale capiamo dai log dove si trova davvero.
    metadata = data.get("metadata", {}) or {}
    phone_call = metadata.get("phone_call", {}) or {}
    for candidate in (
        phone_call.get("external_number"),
        phone_call.get("caller_number"),
        metadata.get("from_number"),
        metadata.get("caller_id"),
    ):
        if candidate:
            return candidate
    return None


def build_summary_email(dealer_nome, dealer_cognome, punto_vendita, motivo, esito, caller_number, summary):
    nome_completo = " ".join(p for p in [dealer_nome, dealer_cognome] if p) or "Non fornito"
    righe = [
        "Nuova chiamata ricevuta dall'assistente AI dealer 1Mobile.",
        "",
        "Dealer: %s" % nome_completo,
        "Punto vendita: %s" % (punto_vendita or "Non fornito"),
        "Numero chiamante: %s" % (caller_number or "Non disponibile"),
        "Motivo della chiamata: %s" % (motivo or "Non specificato"),
        "Esito: %s" % (esito or "Non specificato"),
        "",
        "Riassunto della chiamata:",
        summary or "(nessun riassunto disponibile)",
    ]
    return "\n".join(righe)


def handle_elevenlabs_webhook(raw_body, signature_header):
    from elevenlabs import ElevenLabs  # import locale: dipendenza usata solo qui

    if not ELEVENLABS_WEBHOOK_SECRET:
        raise RuntimeError("ELEVENLABS_WEBHOOK_SECRET non configurata sul server")
    if not NOTIFY_EMAIL:
        raise RuntimeError("UNITEL_NOTIFY_EMAIL non configurata sul server")

    client = ElevenLabs()
    event = client.webhooks.construct_event(
        raw_body.decode("utf-8"),
        signature_header,
        ELEVENLABS_WEBHOOK_SECRET,
    )

    event_type = event.get("type")
    if event_type != "post_call_transcription":
        return {"skipped": event_type}

    data = event.get("data", {}) or {}
    analysis = data.get("analysis", {}) or {}
    collected = analysis.get("data_collection_results", {}) or {}

    dealer_nome = _field(collected, "dealer_nome")
    dealer_cognome = _field(collected, "dealer_cognome")
    punto_vendita = _field(collected, "punto_vendita")
    motivo = _field(collected, "motivo_chiamata")
    esito = _field(collected, "esito")
    summary = analysis.get("transcript_summary", "")
    caller_number = _caller_number(data)

    sys.stderr.write(
        "Webhook chiamata: collected_keys=%s caller_number=%s metadata_keys=%s\n"
        % (list(collected.keys()), caller_number, list((data.get("metadata") or {}).keys()))
    )

    send_email(
        NOTIFY_EMAIL,
        "Nuova chiamata dealer 1Mobile - %s" % (dealer_nome or punto_vendita or "chiamante non identificato"),
        build_summary_email(dealer_nome, dealer_cognome, punto_vendita, motivo, esito, caller_number, summary),
    )
    return {"sent": True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        if self.path == "/":
            self._send_json(200, {"ok": True, "service": "unitel-1mobile-webhook"})
            return
        self.send_error(404, "Not found")

    def do_POST(self):
        if self.path != "/api/elevenlabs-webhook":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b""
        signature = self.headers.get("ElevenLabs-Signature", "")
        try:
            result = handle_elevenlabs_webhook(raw, signature)
            sys.stderr.write("ElevenLabs webhook handled: %s\n" % result)
            self._send_json(200, {"ok": True})
        except Exception:
            sys.stderr.write("Webhook error:\n%s\n" % traceback.format_exc())
            # Rispondiamo comunque 200: se rispondiamo errore, ElevenLabs
            # ritenta la stessa chiamata piu' volte.
            self._send_json(200, {"ok": False})

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if not RESEND_API_KEY:
        sys.stderr.write("ATTENZIONE: RESEND_API_KEY non impostata.\n")
    if not ELEVENLABS_WEBHOOK_SECRET:
        sys.stderr.write("ATTENZIONE: ELEVENLABS_WEBHOOK_SECRET non impostata.\n")
    if not NOTIFY_EMAIL:
        sys.stderr.write("ATTENZIONE: UNITEL_NOTIFY_EMAIL non impostata.\n")
    server = ThreadingHTTPServer(("", port), Handler)
    print("Unitel 1Mobile webhook server in ascolto su http://localhost:%d" % port)
    server.serve_forever()
