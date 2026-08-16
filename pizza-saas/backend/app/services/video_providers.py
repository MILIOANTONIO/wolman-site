"""
Adapter per provider AI foto->video (Promoziona milestone 3) - interfaccia
comune cosi' il resto dell'app non dipende da un fornitore specifico (spec
Promoziona, sez. 13-14: "Do NOT hard-code one vendor"). Un solo adapter
concreto per ora (Kling, economico) - se ne aggiungono altri implementando
la stessa interfaccia, mai cambiando il codice che li chiama.

Nessuna chiamata reale e' mai stata testata contro l'API vera (nessuna
chiave disponibile in questa sessione) - fallisce in modo esplicito e
comprensibile se KLING_API_KEY non e' configurata, invece di un errore
di rete criptico. Stesso schema seguito per DEEPL_API_KEY: si aggiunge la
chiave su Render quando disponibile, il codice e' gia' pronto.
"""
import asyncio
import os
from abc import ABC, abstractmethod

import httpx


class VideoProviderError(Exception):
    pass


class ProviderNotConfigured(VideoProviderError):
    pass


class VideoProvider(ABC):
    name: str
    cost_cents: int  # costo interno stimato per generazione, per il tracking su credit_transactions

    @abstractmethod
    async def generate_image_to_video(self, image_url: str, prompt: str, duration: int) -> str:
        """Invia il job al provider, ritorna un job_id da interrogare con get_status."""

    @abstractmethod
    async def get_status(self, job_id: str) -> dict:
        """Ritorna {'status': 'processing'|'ready'|'failed', 'video_url': str|None, 'error': str|None}."""


class KlingProvider(VideoProvider):
    """
    Kling AI (Kuaishou) - image-to-video, uno dei provider cinesi economici
    scelti per Promoziona. Endpoint/schema JWT secondo la documentazione
    pubblica Kling al momento della scrittura - da riverificare contro la
    doc ufficiale corrente prima del primo uso reale (nessuna chiamata
    testata qui, vedi nota in testa al file).
    """
    name = "kling"
    cost_cents = 150  # stima grezza, da correggere con i costi reali del piano Kling scelto

    BASE_URL = "https://api.klingai.com"

    def __init__(self):
        self.api_key = os.environ.get("KLING_API_KEY")
        if not self.api_key:
            raise ProviderNotConfigured(
                "KLING_API_KEY non configurata - impostala su Render (Environment) per abilitare "
                "la generazione video con AI. Finche' manca, resta disponibile solo il Reel da template."
            )

    async def generate_image_to_video(self, image_url: str, prompt: str, duration: int) -> str:
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=30) as client:
            res = await client.post(
                "/v1/videos/image2video",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"image": image_url, "prompt": prompt, "duration": min(duration, 10)},
            )
            if res.status_code != 200:
                raise VideoProviderError(f"Kling ha rifiutato la richiesta: {res.status_code} {res.text[:300]}")
            return res.json()["data"]["task_id"]

    async def get_status(self, job_id: str) -> dict:
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=30) as client:
            res = await client.get(f"/v1/videos/image2video/{job_id}", headers={"Authorization": f"Bearer {self.api_key}"})
            if res.status_code != 200:
                raise VideoProviderError(f"Kling: impossibile leggere lo stato del job {job_id}")
            data = res.json()["data"]
            status_map = {"submitted": "processing", "processing": "processing", "succeed": "ready", "failed": "failed"}
            return {
                "status": status_map.get(data.get("task_status"), "processing"),
                "video_url": (data.get("task_result") or {}).get("videos", [{}])[0].get("url"),
                "error": data.get("task_status_msg"),
            }


PROVIDERS: dict[str, type[VideoProvider]] = {"kling": KlingProvider}


def get_provider(name: str = "kling") -> VideoProvider:
    cls = PROVIDERS.get(name)
    if not cls:
        raise VideoProviderError(f"Provider video sconosciuto: {name}")
    return cls()


async def poll_until_done(provider: VideoProvider, job_id: str, timeout_seconds: int = 300, interval_seconds: int = 5) -> dict:
    elapsed = 0
    while elapsed < timeout_seconds:
        result = await provider.get_status(job_id)
        if result["status"] in ("ready", "failed"):
            return result
        await asyncio.sleep(interval_seconds)
        elapsed += interval_seconds
    raise VideoProviderError("Timeout in attesa del video generato dal provider AI")
