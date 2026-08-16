"""
Importa il menu da un file caricato dal proprietario: testo (.txt), PDF,
Word (.docx), oppure una foto del menu. Il testo estratto (o l'immagine
stessa, per le foto) viene passato a Claude con tool-use per ottenere un
elenco strutturato di voci pronte da salvare come Offering.
"""
import base64
import io

from docx import Document
from pypdf import PdfReader

from app.services.claude_client import call_claude_with_tools

EXTRACT_MENU_TOOL = {
    "name": "extract_menu_items",
    "description": "Registra l'elenco di voci di menu individuate nel documento/foto.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "ingredients": {"type": "string", "description": "elenco ingredienti separati da virgola, se indicati"},
                        "price_eur": {"type": "number"},
                        "group_name": {"type": "string", "description": "es. Antipasti, Pizze, Bevande"},
                    },
                    "required": ["name", "price_eur"],
                },
            },
        },
        "required": ["items"],
    },
}

IMAGE_MEDIA_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_text(file_bytes: bytes, ext: str) -> str | None:
    if ext == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        # Un PDF scansionato (senza testo selezionabile) restituisce stringa
        # vuota: in quel caso va trattato come immagine, non come testo.
        return text.strip() or None
    if ext in ("docx", "doc"):
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs) or None
    return None


async def extract_menu_items(files: list[tuple[bytes, str]]) -> list[dict]:
    """
    Accetta più file insieme (es. più foto di pagine diverse del menu, o un
    file di testo più alcune foto) e li passa tutti in un solo messaggio a
    Claude, cosi' può unire le voci senza duplicarle tra una pagina e l'altra.
    """
    content: list[dict] = []
    text_parts: list[str] = []
    has_content = False

    for file_bytes, filename in files:
        ext = _ext(filename)
        text = _extract_text(file_bytes, ext)
        if text:
            text_parts.append(f"--- {filename} ---\n{text}")
            has_content = True
        elif ext in IMAGE_MEDIA_TYPES:
            image_b64 = base64.b64encode(file_bytes).decode("ascii")
            content.append({"type": "image", "source": {"type": "base64", "media_type": IMAGE_MEDIA_TYPES[ext], "data": image_b64}})
            has_content = True
        else:
            raise ValueError(
                f"Formato non supportato per '{filename}' (o PDF senza testo leggibile - se è una scansione, carica una foto della pagina invece)"
            )

    if not has_content:
        raise ValueError("Nessun contenuto leggibile nei file caricati")

    instruction = "Estrai le voci di menu da questi documenti/foto (possono essere più pagine dello stesso menu: unisci i piatti ed evita duplicati)."
    if text_parts:
        instruction += "\n\n" + "\n\n".join(text_parts)
    content.append({"type": "text", "text": instruction})

    messages = [{"role": "user", "content": content}]

    system_prompt = (
        "Sei un assistente che estrae voci di menu da documenti o foto per una pizzeria, "
        "anche quando il menu è distribuito su più pagine o foto separate. "
        "Per ogni piatto individua: nome, prezzo in euro, ingredienti (se elencati), "
        "descrizione breve (se presente), categoria/gruppo (es. Antipasti, Pizze, Bevande). "
        "Se lo stesso piatto compare più volte tra le pagine, includilo una sola volta. "
        "Non inventare piatti, ingredienti o prezzi non presenti nei documenti. "
        "Usa lo strumento extract_menu_items per registrare il risultato."
    )

    # max_tokens alto: un menu reale puo' avere decine di voci, ognuna con
    # nome/prezzo/ingredienti/descrizione/categoria - con il limite di
    # default (1024) la risposta veniva troncata a meta' (stop_reason
    # "max_tokens") e il tool_use risultava vuoto, senza errore esplicito.
    response = await call_claude_with_tools(system_prompt, messages, tools=[EXTRACT_MENU_TOOL], max_tokens=8192)
    if response.get("stop_reason") == "max_tokens":
        raise ValueError("Il menu è troppo lungo per essere estratto in un colpo solo: prova a caricare meno pagine/foto per volta")

    content_blocks = response.get("content", [])
    tool_use = next((b for b in content_blocks if b.get("type") == "tool_use" and b.get("name") == "extract_menu_items"), None)
    if not tool_use:
        raise ValueError("Non sono riuscito a individuare voci di menu nel file caricato")

    items = tool_use.get("input", {}).get("items", [])
    return [
        {
            "name": item["name"],
            "description": item.get("description"),
            "ingredients": item.get("ingredients"),
            "price_cents": round(float(item.get("price_eur", 0)) * 100),
            "group_name": item.get("group_name"),
            "unit": None,
            "is_available": True,
        }
        for item in items
        if item.get("name")
    ]
