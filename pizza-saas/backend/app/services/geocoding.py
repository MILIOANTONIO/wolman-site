"""
Geocodifica server-side dell'indirizzo di consegna raccolto dall'AI, usata
per assegnare l'ordine al fattorino piu' vicino e per calcolare il percorso.
Se la chiave non e' configurata o la chiamata fallisce, l'ordine viene
comunque creato senza coordinate - la consegna resta assegnabile, solo senza
criterio di vicinanza (si passa al solo criterio del carico di lavoro).
"""
import sys

import httpx

from app.config import GOOGLE_MAPS_API_KEY

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def geocode_address(address: str, *, region_hint: str | None = None) -> tuple[float, float] | None:
    if not GOOGLE_MAPS_API_KEY or not address or not address.strip():
        return None

    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    if region_hint:
        params["region"] = region_hint

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GEOCODE_URL, params=params)
            data = resp.json()
    except Exception as e:
        sys.stderr.write(f"Geocodifica fallita per '{address}': {e}\n")
        return None

    if data.get("status") != "OK" or not data.get("results"):
        if data.get("status") not in ("ZERO_RESULTS",):
            sys.stderr.write(f"Geocodifica '{address}' -> stato {data.get('status')}: {data.get('error_message', '')}\n")
        return None

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]
