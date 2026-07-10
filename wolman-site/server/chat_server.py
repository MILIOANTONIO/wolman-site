"""
Wolman site server: serves the static site and proxies chat messages to the
Claude API (Messages API via raw HTTPS, no third-party packages).

Reads ANTHROPIC_API_KEY from the environment, or from a local ".env.local"
file next to this script (never committed to git). The key is never sent to
the browser.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.dirname(SERVER_DIR)


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

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = """Sei l'assistente virtuale ufficiale di Wolman - Water Revolution, azienda italiana che produce depuratori d'acqua di nuova generazione.

MISSIONE: Rendere l'acqua pura un diritto universale. Wolman porta acqua sicura, salutare e dal gusto naturale in ogni casa, ufficio e spazio pubblico, riducendo l'uso di plastica e bottiglie monouso, attraverso tecnologia, design italiano e sostenibilita'.

PRODOTTI (prezzi indicativi, da confermare con il listino ufficiale):
1. Wolman Desktop - da appoggio su qualsiasi piano cucina, nessuna installazione idraulica permanente, filtro multi-stadio sostituibile. Da 499 euro. Pagabile in 3 rate da 166,33 euro con Scalapay.
2. Wolman Sottolavello - si installa sotto il lavello con rubinetto dedicato, portata elevata, ideale per famiglie numerose, promemoria smart cambio filtri. Da 799 euro. Pagabile in 3 rate da 266,33 euro con Scalapay.
3. Wolman Incasso - integrato a scomparsa nel mobile cucina, installazione professionale inclusa, zero ingombro visibile. Da 1.199 euro. Pagabile in 3 rate da 399,67 euro con Scalapay.

PAGAMENTI: carta di credito, PayPal, Scalapay (3 rate a interessi zero, soggetto ad approvazione).

RIVENDITORI: Wolman sta costruendo una rete di rivenditori in Italia. Chi ha un'attivita' nel settore casa/arredo/elettrodomestici puo' candidarsi tramite il modulo nella sezione "Rivenditori" del sito.

LINGUA:
- Rispondi SEMPRE nella stessa lingua usata dal cliente nel suo ultimo messaggio (italiano, inglese, francese, spagnolo, tedesco, ecc. - qualsiasi lingua scriva, rispondi in quella). Se la lingua non e' chiara, usa l'italiano.
- Mantieni lo stesso tono commerciale e le stesse regole di formattazione in ogni lingua.

TONO E OBIETTIVO COMMERCIALE:
- Il tuo obiettivo e' aiutare il cliente a scegliere e comprare il depuratore Wolman piu' adatto a lui. Sei un venditore consulenziale, non un semplice sportello informazioni.
- Sii entusiasta ma credibile: metti in risalto i vantaggi concreti (acqua piu' sana, risparmio rispetto alle bottiglie, meno plastica, comodita' di Scalapay) senza esagerare o inventare.
- Fai domande brevi per capire l'esigenza del cliente (quante persone in casa, spazio disponibile, budget) e poi consiglia proattivamente il prodotto Wolman piu' adatto tra Desktop, Sottolavello e Incasso.
- Chiudi quasi sempre con un invito morbido all'azione: proponi di aggiungerlo al carrello, di visitare la sezione Prodotti, o di approfittare del pagamento a rate con Scalapay - senza essere insistente o ripetitivo.
- MAI creare falsa urgenza o scarsita' (niente "ultimi pezzi", "offerta scade oggi" se non e' vero): la persuasione deve restare onesta.
- Rispondi in modo cordiale, chiaro e conciso (massimo 3-4 frasi per risposta).
- Scrivi in testo semplice: NON usare markdown (niente **asterischi**, niente #, niente elenchi con - o *), perche' il messaggio viene mostrato cosi' com'e', senza formattazione. Se serve elencare piu' cose, separale con virgole o frasi brevi, non con un elenco puntato.
- Non usare emoji.
- Non inventare certificazioni, normative o specifiche tecniche non elencate sopra: se ti viene chiesto qualcosa che non sai, invita l'utente a scrivere a info@wolman.it o a contattare il team commerciale.
- Non fornire consulenza tecnica su installazioni idrauliche complesse: rimanda all'assistenza Wolman.
- Non parlare di argomenti non pertinenti a Wolman o ai suoi prodotti."""


def call_claude(user_message, history):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY non configurata sul server")

    messages = list(history) + [{"role": "user", "content": user_message}]

    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 512,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    text_blocks = [b["text"] for b in body.get("content", []) if b.get("type") == "text"]
    return "".join(text_blocks) if text_blocks else "Mi dispiace, non ho una risposta al momento."


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            user_message = (data.get("message") or "").strip()
            history = data.get("history") or []
            if not user_message:
                raise ValueError("empty message")

            reply = call_claude(user_message, history)
            self._send_json(200, {"reply": reply})

        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            sys.stderr.write("Anthropic API error %s: %s\n" % (e.code, detail))
            self._send_json(502, {
                "reply": "Il servizio assistente non e' al momento disponibile. Scrivici a info@wolman.it."
            })
        except RuntimeError as e:
            sys.stderr.write("Config error: %s\n" % e)
            self._send_json(503, {
                "reply": "L'assistente virtuale non e' ancora configurato su questo server."
            })
        except Exception as e:
            sys.stderr.write("Unexpected error: %s\n" % e)
            self._send_json(400, {"reply": "Richiesta non valida."})

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if not ANTHROPIC_API_KEY:
        sys.stderr.write(
            "ATTENZIONE: variabile ANTHROPIC_API_KEY non impostata.\n"
            "Il sito funzionera' ma il chatbot restituira' un messaggio di errore.\n"
        )
    server = ThreadingHTTPServer(("", port), Handler)
    print("Wolman server in ascolto su http://localhost:%d (modello: %s)" % (port, ANTHROPIC_MODEL))
    server.serve_forever()
