"""
Motore di rendering Reel (Promoziona milestone 2): animazione deterministica
di una singola foto sorgente (zoom/pan "Ken Burns" + testo) via ffmpeg, senza
nessuna AI a pagamento - e' il motore VideoProvider "template" della spec;
provider AI a pagamento (Kling, Seedance, ecc.) verranno aggiunti come
adapter separati nella milestone 3, dietro la stessa interfaccia render_reel.

Il binario ffmpeg non e' incluso nel repo (troppo pesante): in locale va
scaricato in pizza-saas/backend/bin/ffmpeg(.exe), su Render lo scarica lo
script di build (vedi render.yaml) in quello stesso path. FFMPEG_BINARY
permette di sovrascrivere il percorso se serve.
"""
import asyncio
import os
import uuid

from app.models import ContentAsset, Reel
from app.services.video_templates import TEMPLATES_BY_ID

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FONT_PATH = os.path.join(_BACKEND_ROOT, "app", "assets", "fonts", "Oswald-Bold.ttf")
REELS_DIR = os.path.join(_BACKEND_ROOT, "uploads", "reels")

_DEFAULT_BIN = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
FFMPEG_BINARY = os.environ.get("FFMPEG_BINARY") or os.path.join(_BACKEND_ROOT, "bin", _DEFAULT_BIN)
if not os.path.exists(FFMPEG_BINARY):
    FFMPEG_BINARY = "ffmpeg"  # fallback: spera che sia sul PATH di sistema


class RenderError(Exception):
    pass


def _ken_burns_filter(ken_burns: str, duration: int, fps: int = 30) -> str:
    """Espressione zoompan per il movimento richiesto dal template - vedi video_templates.py."""
    frames = duration * fps
    if ken_burns == "zoom_in":
        z = "min(zoom+0.0015,1.4)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif ken_burns == "zoom_out":
        z = "if(eq(on,0),1.4,max(zoom-0.0015,1.0))"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif ken_burns == "pan_right":
        z = "1.15"
        x, y = f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
    else:  # pan_left
        z = "1.15"
        x, y = f"(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s=1080x1920:fps={fps}"


def _text_position_y(position: str) -> str:
    if position == "top":
        return "h*0.12"
    if position == "center":
        return "(h-text_h)/2"
    return "h*0.82"  # bottom


async def render_reel(reel: Reel, source_asset: ContentAsset) -> tuple[str, str]:
    """Genera l'mp4 e la thumbnail per un Reel. Ritorna (video_url, thumbnail_url), solleva RenderError se ffmpeg fallisce."""
    template = TEMPLATES_BY_ID.get(reel.template_id)
    if not template:
        raise RenderError(f"Template sconosciuto: {reel.template_id}")
    if source_asset.type != "image":
        raise RenderError("Milestone 2 supporta solo foto come sorgente (non video)")

    source_path = os.path.join(_BACKEND_ROOT, source_asset.source_url.lstrip("/"))
    if not os.path.exists(source_path):
        raise RenderError(f"File sorgente non trovato: {source_asset.source_url}")

    tenant_dir = os.path.join(REELS_DIR, str(reel.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)
    out_name = f"{uuid.uuid4().hex}.mp4"
    thumb_name = f"{uuid.uuid4().hex}.jpg"
    out_path = os.path.join(tenant_dir, out_name)
    thumb_path = os.path.join(tenant_dir, thumb_name)

    duration = template["duration"]
    ken_burns = _ken_burns_filter(template["ken_burns"], duration)

    vf_parts = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        ken_burns,
    ]
    if reel.caption:
        text = reel.caption.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        y_expr = _text_position_y(template["text_position"])
        # ':' e' il separatore tra opzioni di un filtro ffmpeg - nei path Windows (C:/...) va
        # sfuggito, altrimenti "C" viene letto come nome opzione e tutto il resto come valore orfano.
        font_path = _FONT_PATH.replace("\\", "/").replace(":", "\\:")
        vf_parts.append(
            "drawtext=fontfile='%s':text='%s':fontcolor=white:fontsize=64:"
            "box=1:boxcolor=black@0.45:boxborderw=24:x=(w-text_w)/2:y=%s"
            % (font_path, text, y_expr)
        )
    vf = ",".join(vf_parts)

    cmd = [
        FFMPEG_BINARY, "-y",
        "-loop", "1", "-i", source_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        out_path,
    ]
    await _run_ffmpeg(cmd)

    thumb_cmd = [FFMPEG_BINARY, "-y", "-i", out_path, "-vframes", "1", "-q:v", "3", thumb_path]
    await _run_ffmpeg(thumb_cmd)

    return f"/uploads/reels/{reel.tenant_id}/{out_name}", f"/uploads/reels/{reel.tenant_id}/{thumb_name}"


async def _run_ffmpeg(cmd: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RenderError(stderr.decode(errors="replace")[-1500:])
