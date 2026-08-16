"""
Coda di rendering per Promoziona (milestone 2): un asyncio.Queue in-process,
stesso spirito del ciclo di enforcement fatturazione in main.py (un solo loop
in background, niente Redis/worker separato). Va bene per il volume atteso
di un MVP a istanza singola - se il volume di Reel richiedera' piu'
concorrenza o piu' istanze, e' il punto naturale per migrare a Redis+worker
dedicato senza cambiare la forma delle API sopra.
"""
import asyncio
import datetime
import sys
import uuid

from app.db import SessionLocal
from app.models import ContentAsset, Reel, ReelGeneration
from app.services.video_engine import RenderError, render_reel

_queue: "asyncio.Queue[uuid.UUID]" = asyncio.Queue()


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def enqueue_reel(reel_id: uuid.UUID) -> None:
    await _queue.put(reel_id)


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
            video_url, thumbnail_url = await render_reel(reel, source_asset)
        except RenderError as e:
            reel.status = "failed"
            generation.status = "failed"
            generation.error = str(e)[:500]
            generation.completed_at = _now()
            await db.commit()
            sys.stderr.write(f"Rendering Reel {reel_id} fallito: {e}\n")
            return

        reel.status = "ready"
        reel.video_url = video_url
        reel.thumbnail_url = thumbnail_url
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
