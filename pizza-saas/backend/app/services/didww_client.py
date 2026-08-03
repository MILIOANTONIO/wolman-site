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
            resp.raise_for_status()
        return resp.json() if resp.content else {}


async def search_available_dids(country_id: str, city_id: str | None = None, needs_registration: bool | None = None) -> list[dict]:
    params = {"filter[country.id]": country_id, "include": "did_group,did_group.stock_keeping_units"}
    if city_id:
        params["filter[city.id]"] = city_id
    if needs_registration is not None:
        params["filter[did_group.needs_registration]"] = str(needs_registration).lower()

    data = await _request("GET", "/available_dids", params=params)
    return data.get("data", [])


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
        "phone_number": phone_number,
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


async def create_address_verification(*, did_reservation_id: str, address_id: str, encrypted_file_ids: list[str]) -> dict:
    body = {
        "data": {
            "type": "address_verifications",
            "attributes": {"service_description": "Attivazione numero pizza-saas"},
            "relationships": {
                "dids": {"data": [{"type": "did_reservations", "id": did_reservation_id}]},
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
