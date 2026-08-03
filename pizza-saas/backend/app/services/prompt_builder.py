"""
Genera il system prompt di un tenant per un dato canale (voice/whatsapp) a
partire da un template Jinja2. Un solo builder per entrambi i canali, cosi'
menu/orari/regole non vanno mai fuori sincronia tra voce e WhatsApp.

Il template è scelto in base a tenant.category: oggi esiste solo
"pizzeria.md.jinja2" (MVP); le altre categorie della famiglia
"servizi a prenotazione" (parrucchiere, massaggi, idraulico, hotel, ...)
useranno "generic.md.jinja2" finché non avranno un template dedicato, senza
bisogno di toccare questo codice.
"""
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Offering, Tenant, TenantSettings

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")

_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(enabled_extensions=()),  # testo per un LLM, non HTML
    trim_blocks=True,
    lstrip_blocks=True,
)

TEMPLATE_BY_CATEGORY = {
    "pizzeria": "pizzeria.md.jinja2",
}
DEFAULT_TEMPLATE = "generic.md.jinja2"


async def build_agent_prompt(db: AsyncSession, tenant: Tenant, channel: str, transfer_number: str | None = None) -> str:
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    offerings = (
        await db.execute(select(Offering).where(Offering.tenant_id == tenant.id).order_by(Offering.group_name, Offering.name))
    ).scalars().all()

    template_name = TEMPLATE_BY_CATEGORY.get(tenant.category, DEFAULT_TEMPLATE)
    template = _env.get_template(template_name)
    return template.render(
        tenant=tenant,
        settings=settings_row,
        offerings=offerings,
        channel=channel,
        transfer_number=transfer_number,
    )
