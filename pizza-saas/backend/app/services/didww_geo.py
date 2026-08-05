"""
Trova numeri DIDWW disponibili vicino all'indirizzo del tenant, per non
proporre mai (es.) un numero di Milano a chi ha il locale a Milazzo - vedi
richiesta esplicita del titolare.

DIDWW non offre un filtro diretto "vicino a questo indirizzo": si cerca per
citta' esatta, e se non c'e' nulla si scende di un livello (capoluogo di
provincia, poi regione) finche' non si trova disponibilita' o si esaurisce
la zona - non si esce mai dalla provincia/regione di appartenenza.
"""
import sys

from app.services import didww_client

# Provincia (sigla) -> regione, per il fallback quando la citta' esatta del
# tenant non ha numeri DIDWW disponibili (dato geografico statico, stabile).
REGION_BY_PROVINCE = {
    "AQ": "Abruzzo", "CH": "Abruzzo", "PE": "Abruzzo", "TE": "Abruzzo",
    "MT": "Basilicata", "PZ": "Basilicata",
    "CZ": "Calabria", "CS": "Calabria", "KR": "Calabria", "RC": "Calabria", "VV": "Calabria",
    "AV": "Campania", "BN": "Campania", "CE": "Campania", "NA": "Campania", "SA": "Campania",
    "BO": "Emilia-Romagna", "FC": "Emilia-Romagna", "FE": "Emilia-Romagna", "MO": "Emilia-Romagna",
    "PC": "Emilia-Romagna", "PR": "Emilia-Romagna", "RA": "Emilia-Romagna", "RE": "Emilia-Romagna", "RN": "Emilia-Romagna",
    "GO": "Friuli-Venezia Giulia", "PN": "Friuli-Venezia Giulia", "TS": "Friuli-Venezia Giulia", "UD": "Friuli-Venezia Giulia",
    "FR": "Lazio", "LT": "Lazio", "RI": "Lazio", "RM": "Lazio", "VT": "Lazio",
    "GE": "Liguria", "IM": "Liguria", "SP": "Liguria", "SV": "Liguria",
    "BG": "Lombardia", "BS": "Lombardia", "CO": "Lombardia", "CR": "Lombardia", "LC": "Lombardia",
    "LO": "Lombardia", "MB": "Lombardia", "MI": "Lombardia", "MN": "Lombardia", "PV": "Lombardia", "SO": "Lombardia", "VA": "Lombardia",
    "AN": "Marche", "AP": "Marche", "FM": "Marche", "MC": "Marche", "PU": "Marche",
    "CB": "Molise", "IS": "Molise",
    "AL": "Piemonte", "AT": "Piemonte", "BI": "Piemonte", "CN": "Piemonte", "NO": "Piemonte", "TO": "Piemonte", "VB": "Piemonte", "VC": "Piemonte",
    "BA": "Puglia", "BT": "Puglia", "BR": "Puglia", "FG": "Puglia", "LE": "Puglia", "TA": "Puglia",
    "CA": "Sardegna", "NU": "Sardegna", "OR": "Sardegna", "SS": "Sardegna", "SU": "Sardegna",
    "AG": "Sicilia", "CL": "Sicilia", "CT": "Sicilia", "EN": "Sicilia", "ME": "Sicilia", "PA": "Sicilia", "RG": "Sicilia", "SR": "Sicilia", "TP": "Sicilia",
    "AR": "Toscana", "FI": "Toscana", "GR": "Toscana", "LI": "Toscana", "LU": "Toscana", "MS": "Toscana", "PI": "Toscana", "PO": "Toscana", "PT": "Toscana", "SI": "Toscana",
    "BZ": "Trentino-Alto Adige", "TN": "Trentino-Alto Adige",
    "PG": "Umbria", "TR": "Umbria",
    "AO": "Valle d'Aosta",
    "BL": "Veneto", "PD": "Veneto", "RO": "Veneto", "TV": "Veneto", "VE": "Veneto", "VI": "Veneto", "VR": "Veneto",
}

# Provincia (sigla) -> capoluogo, secondo livello di fallback prima della regione.
PROVINCE_CAPITAL = {
    "AG": "Agrigento", "AL": "Alessandria", "AN": "Ancona", "AO": "Aosta", "AP": "Ascoli Piceno",
    "AQ": "L Aquila", "AR": "Arezzo", "AT": "Asti", "AV": "Avellino", "BA": "Bari", "BG": "Bergamo",
    "BI": "Biella", "BL": "Belluno", "BN": "Benevento", "BO": "Bologna", "BR": "Brindisi", "BS": "Brescia",
    "BT": "Andria", "BZ": "Bolzano", "CA": "Cagliari", "CB": "Campobasso", "CE": "Caserta",
    "CH": "Chieti", "CL": "Caltanissetta", "CN": "Cuneo", "CO": "Como", "CR": "Cremona", "CS": "Cosenza",
    "CT": "Catania", "CZ": "Catanzaro", "EN": "Enna", "FC": "Forli", "FE": "Ferrara", "FG": "Foggia",
    "FI": "Firenze", "FM": "Fermo", "FR": "Frosinone", "GE": "Genova", "GO": "Gorizia", "GR": "Grosseto",
    "IM": "Imperia", "IS": "Isernia", "KR": "Crotone", "LC": "Lecco", "LE": "Lecce", "LI": "Livorno",
    "LO": "Lodi", "LT": "Latina", "LU": "Lucca", "MB": "Monza", "MC": "Macerata", "ME": "Messina",
    "MI": "Milano", "MN": "Mantova", "MO": "Modena", "MS": "Massa", "MT": "Matera", "NA": "Napoli",
    "NO": "Novara", "NU": "Nuoro", "OR": "Oristano", "PA": "Palermo", "PC": "Piacenza", "PD": "Padova",
    "PE": "Pescara", "PG": "Perugia", "PI": "Pisa", "PN": "Pordenone", "PO": "Prato", "PR": "Parma",
    "PT": "Pistoia", "PU": "Pesaro", "PV": "Pavia", "PZ": "Potenza", "RA": "Ravenna", "RC": "Reggio Calabria",
    "RE": "Reggio Emilia", "RG": "Ragusa", "RI": "Rieti", "RM": "Roma", "RN": "Rimini", "RO": "Rovigo",
    "SA": "Salerno", "SI": "Siena", "SO": "Sondrio", "SP": "La Spezia", "SR": "Siracusa", "SS": "Sassari",
    "SU": "Carbonia", "SV": "Savona", "TA": "Taranto", "TE": "Teramo", "TN": "Trento", "TO": "Torino",
    "TP": "Trapani", "TR": "Terni", "TS": "Trieste", "TV": "Treviso", "UD": "Udine", "VA": "Varese",
    "VB": "Verbania", "VC": "Vercelli", "VE": "Venezia", "VI": "Vicenza", "VR": "Verona", "VT": "Viterbo", "VV": "Vibo Valentia",
}

# I pochi grandi capoluoghi che nel catalogo citta' di DIDWW risultano in
# inglese invece che in italiano (verificato empiricamente contro l'API).
CITY_NAME_ALIASES = {"milano": "Milan", "roma": "Rome", "napoli": "Naples"}

_country_id_cache: str | None = None
_region_id_cache: dict[str, str] = {}


async def _italy_country_id() -> str | None:
    global _country_id_cache
    if _country_id_cache:
        return _country_id_cache
    try:
        data = await didww_client._request("GET", "/countries", params={"filter[iso]": "IT"})
    except Exception as e:
        sys.stderr.write(f"Lookup country DIDWW fallito: {e}\n")
        return None
    results = data.get("data", [])
    if not results:
        return None
    _country_id_cache = results[0]["id"]
    return _country_id_cache


async def _find_city_id(country_id: str, name: str) -> str | None:
    try:
        data = await didww_client._request("GET", "/cities", params={"filter[country.id]": country_id, "filter[name]": name})
    except Exception as e:
        sys.stderr.write(f"Lookup citta' DIDWW '{name}' fallito: {e}\n")
        return None
    results = data.get("data", [])
    return results[0]["id"] if results else None


async def _region_id(country_id: str, region_name: str) -> str | None:
    if region_name in _region_id_cache:
        return _region_id_cache[region_name]
    try:
        data = await didww_client._request("GET", f"/countries/{country_id}/regions")
    except Exception as e:
        sys.stderr.write(f"Lookup regioni DIDWW fallito: {e}\n")
        return None
    for r in data.get("data", []):
        _region_id_cache[r["attributes"]["name"]] = r["id"]
    return _region_id_cache.get(region_name)


async def _search_by_city_name(country_id: str, city_name: str) -> list[dict]:
    candidates = [city_name]
    alias = CITY_NAME_ALIASES.get(city_name.strip().lower())
    if alias:
        candidates.append(alias)

    for candidate in candidates:
        city_id = await _find_city_id(country_id, candidate)
        if not city_id:
            continue
        numbers = await didww_client.search_available_dids(country_id, city_id=city_id)
        if numbers:
            return numbers
    return []


async def find_numbers_for_tenant(tenant_city: str | None, tenant_province: str | None) -> dict:
    """
    Ritorna {"match_level": "citta"|"provincia"|"regione"|"nessuno",
    "match_label": str | None, "numbers": [...]} - i numeri sono sempre
    filtrati sulla zona del tenant, mai su citta' scollegate dal suo
    indirizzo (es. mai un numero di Milano per un locale a Milazzo).
    """
    country_id = await _italy_country_id()
    if not country_id:
        return {"match_level": "nessuno", "match_label": None, "numbers": []}

    province = (tenant_province or "").strip().upper()

    if tenant_city:
        numbers = await _search_by_city_name(country_id, tenant_city)
        if numbers:
            return {"match_level": "citta", "match_label": tenant_city, "numbers": numbers}

    capital = PROVINCE_CAPITAL.get(province)
    if capital and capital.lower() != (tenant_city or "").strip().lower():
        numbers = await _search_by_city_name(country_id, capital)
        if numbers:
            return {"match_level": "provincia", "match_label": capital, "numbers": numbers}

    region_name = REGION_BY_PROVINCE.get(province)
    if region_name:
        region_id = await _region_id(country_id, region_name)
        if region_id:
            numbers = await didww_client.search_available_dids(country_id, region_id=region_id)
            if numbers:
                return {"match_level": "regione", "match_label": region_name, "numbers": numbers}

    return {"match_level": "nessuno", "match_label": None, "numbers": []}
