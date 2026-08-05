"""
Client per l'API DIDWW v3 (JSON:API) usata per il flusso "numero locale con
KYC": ricerca numeri disponibili, prenotazione, identità/indirizzo,
caricamento documenti, verifica, ordine finale.

Basato sulla documentazione reale (doc.didww.com/api3/2026-04-16/) verificata
per: available_dids, did_reservations, identities, addresses,
address_verifications, orders. UN PEZZO NON è stato possibile confermare con
certezza dalla documentazione pubblica: il formato esatto di upload per
`encrypted_files` (qui implementato con il pattern JSON:API standard,
contenuto file in base64) - va validato contro l'ambiente sandbox DIDWW o la
loro collection Postman prima del primo uso reale, vedi commento sotto.

Nota: DIDWW richiede che la ricerca "available_dids" sia abilitata da
Sales/Customer Service sull'account prima di poterla usare via API.
"""
import base64
import sys

import httpx

from app.config import DIDWW_API_KEY, DIDWW_BASE_URL

HEADERS = {
    "Api-Key": DIDWW_API_KEY or "",
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
}


def _require_key():
    if not DIDWW_API_KEY:
        raise RuntimeError("DIDWW_API_KEY non configurata sul server")


async def _request(method: str, path: str, json_body: dict | None = None, params: dict | None = None) -> dict:
    _require_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, f"{DIDWW_BASE_URL}{path}", json=json_body, params=params, headers=HEADERS)
        if resp.status_code >= 400:
            sys.stderr.write(f"DIDWW API error {method} {path} {resp.status_code}: {resp.text}\n")
            detail = resp.text
            try:
                errors = resp.json().get("errors", [])
                if errors:
                    detail = "; ".join(e.get("detail") or e.get("title") or "" for e in errors)
            except Exception:
                pass
            raise RuntimeError(f"DIDWW {resp.status_code}: {detail}")
        return resp.json() if resp.content else {}


async def search_available_dids(
    country_id: str, city_id: str | None = None, region_id: str | None = None, needs_registration: bool | None = None,
) -> list[dict]:
    """
    Ritorna una lista appiattita e pronta da mostrare in UI: ogni numero
    disponibile con il nome della sua citta'/zona, l'sku (necessario per
    prenotare) e il prezzo - senza che il chiamante debba districarsi nel
    formato JSON:API con "included".
    """
    params = {"filter[country.id]": country_id, "include": "did_group,did_group.city,did_group.stock_keeping_units"}
    if city_id:
        params["filter[city.id]"] = city_id
    if region_id:
        params["filter[region.id]"] = region_id
    if needs_registration is not None:
        params["filter[did_group.needs_registration]"] = str(needs_registration).lower()

    data = await _request("GET", "/available_dids", params=params)

    cities_by_id = {inc["id"]: inc["attributes"]["name"] for inc in data.get("included", []) if inc["type"] == "cities"}
    skus_by_id = {inc["id"]: inc["attributes"] for inc in data.get("included", []) if inc["type"] == "stock_keeping_units"}
    groups_by_id = {}
    for inc in data.get("included", []):
        if inc["type"] != "did_groups":
            continue
        city_rel = (inc.get("relationships", {}).get("city", {}).get("data") or {}).get("id")
        sku_rels = inc.get("relationships", {}).get("stock_keeping_units", {}).get("data") or []
        sku_id = sku_rels[0]["id"] if sku_rels else None
        groups_by_id[inc["id"]] = {
            "city_name": cities_by_id.get(city_rel),
            "sku_id": sku_id,
            "needs_registration": inc.get("meta", {}).get("needs_registration"),
            **(skus_by_id.get(sku_id) or {}),
        }

    results = []
    for did in data.get("data", []):
        group_id = (did.get("relationships", {}).get("did_group", {}).get("data") or {}).get("id")
        group = groups_by_id.get(group_id, {})
        results.append({
            "available_did_id": did["id"],
            "number": did["attributes"]["number"],
            "city_name": group.get("city_name"),
            "sku_id": group.get("sku_id"),
            "needs_registration": group.get("needs_registration"),
            "setup_price": group.get("setup_price"),
            "monthly_price": group.get("monthly_price"),
        })
    return results


async def reserve_did(available_did_id: str) -> dict:
    body = {
        "data": {
            "type": "did_reservations",
            "attributes": {"description": "pizza-saas"},
            "relationships": {"available_did": {"data": {"type": "available_dids", "id": available_did_id}}},
        }
    }
    data = await _request("POST", "/did_reservations", json_body=body)
    return data["data"]


async def create_identity(*, identity_type: str, first_name: str, last_name: str, contact_email: str, phone_number: str, company_name: str | None = None, company_reg_number: str | None = None) -> str:
    attributes = {
        "identity_type": identity_type,  # "personal" o "business"
        "first_name": first_name,
        "last_name": last_name,
        "contact_email": contact_email,
        # DIDWW rifiuta con 422 qualunque carattere non numerico (niente "+"
        # o spazi) - l'utente puo' scriverlo come preferisce, ripuliamo qui.
        "phone_number": "".join(c for c in phone_number if c.isdigit()),
    }
    if identity_type == "business":
        attributes["company_name"] = company_name
        attributes["company_reg_number"] = company_reg_number

    body = {"data": {"type": "identities", "attributes": attributes}}
    data = await _request("POST", "/identities", json_body=body)
    return data["data"]["id"]


async def create_address(*, identity_id: str, country_id: str, city_name: str, postal_code: str, address: str) -> str:
    body = {
        "data": {
            "type": "addresses",
            "attributes": {"city_name": city_name, "postal_code": postal_code, "address": address},
            "relationships": {
                "identity": {"data": {"type": "identities", "id": identity_id}},
                "country": {"data": {"type": "countries", "id": country_id}},
            },
        }
    }
    data = await _request("POST", "/addresses", json_body=body)
    return data["data"]["id"]


async def upload_encrypted_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    """
    NON VERIFICATO CONTRO LA DOCUMENTAZIONE REALE: la pagina "Create Encrypted
    File" non è stata raggiungibile durante la ricerca. Implementato secondo
    il pattern JSON:API standard usato dalle altre risorse DIDWW (contenuto
    base64 in un attributo "content"). Prima di andare in produzione,
    verificare questo endpoint contro la sandbox DIDWW o la loro Postman
    collection (https://www.postman.com/didww-api/workspace/didww-api3-documentation)
    e correggere se il formato reale è diverso (es. multipart, o due passaggi
    con URL di upload pre-firmato).
    """
    body = {
        "data": {
            "type": "encrypted_files",
            "attributes": {
                "filename": filename,
                "content_type": content_type,
                "content": base64.b64encode(file_bytes).decode("ascii"),
            },
        }
    }
    data = await _request("POST", "/encrypted_files", json_body=body)
    return data["data"]["id"]


async def create_address_verification(*, did_id: str, address_id: str, encrypted_file_ids: list[str]) -> dict:
    # Va referenziato il DID reale (risorsa "dids"), non la prenotazione -
    # verificato contro un ordine reale gia' piazzato: la prenotazione da
    # sola non e' accettata come riferimento valido per la verifica.
    body = {
        "data": {
            "type": "address_verifications",
            "attributes": {"service_description": "Attivazione numero pizza-saas"},
            "relationships": {
                "dids": {"data": [{"type": "dids", "id": did_id}]},
                "address": {"data": {"type": "addresses", "id": address_id}},
                "onetime_files": {"data": [{"type": "encrypted_files", "id": fid} for fid in encrypted_file_ids]},
            },
        }
    }
    data = await _request("POST", "/address_verifications", json_body=body)
    return data["data"]


async def get_verification_status(verification_id: str) -> dict:
    data = await _request("GET", f"/address_verifications/{verification_id}")
    return data["data"]


async def find_did_by_number(number: str) -> dict | None:
    """
    Trova la risorsa "dids" (il numero effettivamente provisionato, diverso
    dalla prenotazione/ordine) per capire se e' davvero attivo:
    attributes.awaiting_registration=True finche' la verifica KYC non e'
    approvata, poi passa a False; blocked/terminated segnalano problemi.
    """
    data = await _request("GET", "/dids", params={"filter[number]": number})
    results = data.get("data", [])
    return results[0] if results else None


async def terminate_did(did_id: str) -> dict:
    """
    Cancella davvero il numero (rilascio definitivo, smette di essere
    fatturato da DIDWW) - "terminated" e' l'unico attributo di stato
    modificabile via PATCH su questa risorsa (verificato: "blocked",
    "status", "state", "active", "suspended" sono tutti rifiutati dall'API
    con "Param not allowed"). Non reversibile: usare solo dopo il periodo di
    grazia per mancato pagamento, mai per una sospensione temporanea.
    """
    body = {"data": {"type": "dids", "id": did_id, "attributes": {"terminated": True}}}
    data = await _request("PATCH", f"/dids/{did_id}", json_body=body)
    return data["data"]


async def create_order(*, did_reservation_id: str, sku_id: str) -> dict:
    body = {
        "data": {
            "type": "orders",
            "attributes": {
                "allow_back_ordering": False,
                "items": [{"type": "did_order_items", "attributes": {"did_reservation_id": did_reservation_id, "sku_id": sku_id}}],
            },
        }
    }
    data = await _request("POST", "/orders", json_body=body)
    return data["data"]


async def get_requirements(country_id: str, did_group_type_id: str | None = None) -> list[dict]:
    """Documenti/campi obbligatori per attivare un numero in un dato paese - da mostrare nel wizard admin prima di chiedere i documenti giusti."""
    params = {"filter[country.id]": country_id}
    if did_group_type_id:
        params["filter[did_group_type.id]"] = did_group_type_id
    data = await _request("GET", "/requirements", params=params)
    return data.get("data", [])
