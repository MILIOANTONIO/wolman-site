"""
Traduzione testi via DeepL, con cache in translation_cache condivisa tra
tutti i tenant (stesso testo sorgente = stesso hash, non importa di chi e').
Usata sia per tradurre in scrittura (quando un piatto o l'headline vengono
salvati - vedi onboarding.py) sia dall'endpoint pubblico per le stringhe
fisse del template (vedi routers/public.py).
"""
import hashlib
import re

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEEPL_API_KEY
from app.models import TranslationCache

DEEPL_TARGET = {"en": "EN-GB", "fr": "FR", "de": "DE", "es": "ES"}
SUPPORTED_LANGS = list(DEEPL_TARGET.keys())
MAX_TEXTS_PER_REQUEST = 80
MAX_TEXT_LENGTH = 500

# DeepL tratta alcuni termini regionali come nomi propri e non li traduce
# (es. "fior di latte" resta tale e quale) - per un cliente straniero che
# legge il menu ha piu' senso il termine generico.
CULINARY_SIMPLIFICATIONS = {
    "fior di latte": "formaggio",
}


def _simplify_for_translation(text: str) -> str:
    for term, replacement in CULINARY_SIMPLIFICATIONS.items():
        text = re.sub(re.escape(term), replacement, text, flags=re.IGNORECASE)
    return text


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def translate_batch(db: AsyncSession, texts: list[str], target_lang: str) -> list[str]:
    """Traduce una lista di testi italiani verso target_lang (en/fr/de/es), usando/alimentando la cache
    condivisa. Nessun limite di lunghezza qui: se serve tradurre piu' di MAX_TEXTS_PER_REQUEST testi in
    un colpo (es. import di un menu con 60+ piatti), spezzetta internamente in piu' chiamate DeepL invece
    di troncare in silenzio - il limite duro resta solo sull'endpoint pubblico (vedi routers/public.py),
    che e' l'unico raggiungibile senza login."""
    target_lang = target_lang.lower()
    if target_lang not in DEEPL_TARGET:
        raise ValueError(f"Lingua non supportata: {target_lang}")
    if not DEEPL_API_KEY:
        raise RuntimeError("DEEPL_API_KEY non configurata")

    texts = [(t or "")[:MAX_TEXT_LENGTH] for t in texts]
    if len(texts) > MAX_TEXTS_PER_REQUEST:
        results: list[str] = []
        for i in range(0, len(texts), MAX_TEXTS_PER_REQUEST):
            results.extend(await translate_batch(db, texts[i:i + MAX_TEXTS_PER_REQUEST], target_lang))
        return results

    hashes = [_text_hash(t) for t in texts]

    cached_rows = (
        await db.execute(
            select(TranslationCache).where(TranslationCache.text_hash.in_(hashes), TranslationCache.target_lang == target_lang)
        )
    ).scalars().all()
    cache_by_hash = {row.text_hash: row.translated_text for row in cached_rows}

    missing_by_hash: dict[str, str] = {}
    for i, h in enumerate(hashes):
        if h not in cache_by_hash and texts[i].strip() and h not in missing_by_hash:
            missing_by_hash[h] = texts[i]

    if missing_by_hash:
        deepl_lang = DEEPL_TARGET[target_lang]
        host = "api-free.deepl.com" if DEEPL_API_KEY.endswith(":fx") else "api.deepl.com"
        simplified_texts = [_simplify_for_translation(v) for v in missing_by_hash.values()]
        # httpx vuole un dict con valore-lista per chiavi ripetute (es. piu' "text"),
        # non una lista di tuple: passata come lista viene trattata come stream sincrono
        # e rompe la richiesta su AsyncClient.
        params = {"text": simplified_texts, "target_lang": deepl_lang, "source_lang": "IT"}
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                f"https://{host}/v2/translate",
                headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
                data=params,
            )
        if res.status_code != 200:
            raise RuntimeError(f"Errore DeepL ({res.status_code})")
        translated = [t["text"] for t in res.json().get("translations", [])]
        for h, translated_text in zip(missing_by_hash.keys(), translated):
            cache_by_hash[h] = translated_text
            db.add(TranslationCache(text_hash=h, target_lang=target_lang, source_text=missing_by_hash[h], translated_text=translated_text))
        try:
            await db.commit()
        except IntegrityError:
            # un'altra richiesta concorrente ha gia' scritto la stessa cache nel frattempo: non e' un errore.
            await db.rollback()

    return [cache_by_hash.get(h, texts[i]) for i, h in enumerate(hashes)]


async def translate_to_all_langs(db: AsyncSession, texts: list[str]) -> dict[str, list[str]]:
    """Traduce la stessa lista di testi in tutte le lingue supportate. Ritorna {lang: [testi tradotti nell'ordine originale]}."""
    result: dict[str, list[str]] = {}
    for lang in SUPPORTED_LANGS:
        result[lang] = await translate_batch(db, texts, lang)
    return result
