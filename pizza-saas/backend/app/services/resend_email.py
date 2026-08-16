"""
Invio email transazionali via Resend, porting diretto del pattern collaudato
in wolman-site/server/chat_server.py e unitel-1mobile/server/webhook_server.py.
"""
import sys

import httpx

from app.config import RESEND_API_KEY, RESEND_FROM, RESEND_URL


async def send_email(to_address: str, subject: str, text_body: str):
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY non configurata sul server")

    payload = {
        "from": RESEND_FROM,
        "to": [to_address],
        "subject": subject,
        "text": text_body,
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        # Senza uno User-Agent "normale", Cloudflare (davanti a Resend) blocca
        # la richiesta come bot (errore 1010) prima che arrivi a Resend.
        "User-Agent": "pizza-saas-backend/1.0",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(RESEND_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            sys.stderr.write(f"Resend API error {resp.status_code}: {resp.text}\n")
            resp.raise_for_status()
        return resp.json()


def build_activation_email(business_name: str) -> str:
    return (
        f"Ciao,\n\nIl tuo account {business_name} è ora attivo! "
        "Il tuo agente AI e il numero di telefono sono configurati e pronti a ricevere chiamate.\n\n"
        "Accedi alla dashboard per vedere gli ordini in arrivo in tempo reale.\n\n"
        "A presto!"
    )
