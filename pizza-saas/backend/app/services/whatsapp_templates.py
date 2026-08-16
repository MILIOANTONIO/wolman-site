"""
Frasi per stato, usate come variabile {{3}} nel template Meta approvato
"order_status_update" ("Ciao {{1}}! Aggiornamento sul tuo ordine da {{2}}: {{3}}."):
un solo template per velocizzare l'approvazione Meta, invece di uno per stato.
"""
STATUS_PHRASES = {
    "ricevuto": "abbiamo ricevuto il tuo ordine",
    "in_forno": "è in forno",
    "pronta": "è pronto, puoi venire a ritirarlo" ,
    "in_consegna": "è uscito per la consegna",
    "consegnata": "è stato consegnato, buon appetito",
    "annullato": "è stato annullato",
}


def phrase_for_status(status: str) -> str:
    return STATUS_PHRASES.get(status, f"stato aggiornato: {status}")
