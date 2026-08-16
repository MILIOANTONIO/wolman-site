"""
Coda di rendering per Promoziona: un asyncio.Queue in-process, stesso spirito
del ciclo di enforcement fatturazione in main.py (un solo loop in background,
niente Redis/worker separato). Va bene per il volume atteso di un MVP a
istanza singola - se il volume di Reel richiedera' piu' concorrenza o piu'
istanze, e' il punto naturale per migrare a Redis+worker dedicato senza
cambiare la forma delle API sopra.

Due percorsi in base a Reel.mode:
- "template": rendering deterministico locale (video_engine.py, milestone 2).
- "ai_video": provider AI esterno (video_providers.py, milestone 3) - costo
  addebitato sul ledger esistente (services/billing.py), mai gratis.
"""
import asyncio
import datetime
import os
import sys
import uuid

import httpx

from app.db import SessionLocal
from app.models import ContentAsset, Reel, ReelGeneration, Tenant
from app.services import billing
from app.services.video_engine import REELS_DIR, RenderError, render_reel
from app.services.video_providers import ProviderNotConfigured, VideoProviderError, get_provider, poll_until_done

_queue: "asyncio.Queue[uuid.UUID]" = asyncio.Queue()

# Render espone automaticamente l'URL pubblico del servizio in questa variabile - serve perche'
# i provider AI esterni devono scaricare l'immagine sorgente da un URL raggiungibile, non da un
# path locale. In locale non e' impostata: la modalita' ai_video semplicemente non e' testabile
# fuori da Render, coerente col fatto che serve comunque una chiave API reale.
_PUBLIC_BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def enqueue_reel(reel_id: uuid.UUID) -> None:
    await _queue.put(reel_id)


async def _download_video(url: str, dest_path: str) -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("GET", url) as res:
            if res.status_code != 200:
                raise VideoProviderError(f"Download del video generato fallito: {res.status_code}")
            with open(dest_path, "wb") as f:
                async for chunk in res.aiter_bytes():
                    f.write(chunk)


async def _process_template(reel: Reel, source_asset: ContentAsset) -> tuple[str, str]:
    return await render_reel(reel, source_asset)


async def _process_ai_video(db, reel: Reel, tenant: Tenant, source_asset: ContentAsset) -> tuple[str, str]:
    provider = get_provider("kling")  # solleva ProviderNotConfigured se manca la chiave

    image_url = f"{_PUBLIC_BASE_URL}{source_asset.source_url}"
    job_id = await provider.generate_image_to_video(image_url, reel.prompt or "", reel.duration)
    result = await poll_until_done(provider, job_id)
    if result["status"] != "ready" or not result.get("video_url"):
        raise VideoProviderError(result.get("error") or "Generazione fallita presso il provider AI")

    tenant_dir = os.path.join(REELS_DIR, str(reel.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    out_name = f"{uuid.uuid4().hex}.mp4"
    out_path = os.path.join(tenant_dir, out_name)
    await _download_video(result["video_url"], out_path)

    await billing.charge_reel_ai_generation(
        db, tenant, provider.cost_cents, f"Generazione Reel AI ({provider.name})"
    )

    return f"/uploads/reels/{reel.tenant_id}/{out_name}", ""


async def _process_one(reel_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        reel = await db.get(Reel, reel_id)
        if not reel:
            return
        source_asset = await db.get(ContentAsset, reel.source_asset_id) if reel.source_asset_id else None
        if not source_asset:
            reel.status = "failed"
            await db.commit()
            sys.stderr.write(f"Rendering Reel {reel_id} fallito: nessun contenuto sorgente collegato\n")
            return

        generation = ReelGeneration(reel_id=reel.id, status="rendering")
        db.add(generation)
        reel.status = "rendering"
        await db.commit()

        try:
            if reel.mode == "ai_video":
                tenant = await db.get(Tenant, reel.tenant_id)
                video_url, thumbnail_url = await _process_ai_video(db, reel, tenant, source_asset)
            else:
                video_url, thumbnail_url = await _process_template(reel, source_asset)
        except (RenderError, VideoProviderError, ProviderNotConfigured) as e:
            reel.status = "failed"
            generation.status = "failed"
            generation.error = str(e)[:500]
            generation.completed_at = _now()
            await db.commit()
            sys.stderr.write(f"Rendering Reel {reel_id} fallito: {e}\n")
            return

        reel.status = "ready"
        reel.video_url = video_url
        reel.thumbnail_url = thumbnail_url or None
        generation.status = "ready"
        generation.completed_at = _now()
        await db.commit()


async def worker_loop() -> None:
    while True:
        reel_id = await _queue.get()
        try:
            await _process_one(reel_id)
        except Exception as e:
            sys.stderr.write(f"Coda rendering Reel: errore inatteso su {reel_id}: {e}\n")
        finally:
            _queue.task_done()
