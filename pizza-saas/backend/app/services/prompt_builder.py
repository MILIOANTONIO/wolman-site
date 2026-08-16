"""
Genera il system prompt di un tenant per un dato canale (voice/whatsapp) a
partire da un template Jinja2. Un solo builder per entrambi i canali, cosi'
menu/orari/regole non vanno mai fuori sincronia tra voce e WhatsApp.

tenant.category è testo libero (pizzeria, ristorante, kebab, ...): oggi
esiste un solo template ("pizzeria.md.jinja2", generico abbastanza da
adattarsi a qualsiasi locale che prende ordini cibo/prenotazioni tavoli) e
lo si usa sempre, qualunque sia il testo in category - il nome del tipo di
attività viene scritto nel prompt cosi' com'è (vedi business_type nel
template). Le prossime famiglie di attività non-cibo (parrucchiere, hotel,
idraulico, ...) avranno template dedicati mappati qui in futuro.
"""
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Offering, Promotion, Tenant, TenantSettings

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")

_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(enabled_extensions=()),  # testo per un LLM, non HTML
    trim_blocks=True,
    lstrip_blocks=True,
)

DEFAULT_TEMPLATE = "pizzeria.md.jinja2"


async def render_template_prompt(db: AsyncSession, tenant: Tenant, channel: str, transfer_number: str | None = None) -> str:
    """Genera il prompt dal template, ignorando eventuali override manuali - usato per rigenerare da zero."""
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    offerings = (
        await db.execute(select(Offering).where(Offering.tenant_id == tenant.id).order_by(Offering.group_name, Offering.name))
    ).scalars().all()
    promotions = (
        await db.execute(select(Promotion).where(Promotion.tenant_id == tenant.id, Promotion.is_active.is_(True)).order_by(Promotion.created_at))
    ).scalars().all()

    template = _env.get_template(DEFAULT_TEMPLATE)
    return template.render(
        tenant=tenant,
        settings=settings_row,
        offerings=offerings,
        promotions=promotions,
        channel=channel,
        transfer_number=transfer_number,
    )


async def build_agent_prompt(db: AsyncSession, tenant: Tenant, channel: str, transfer_number: str | None = None) -> str:
    """Prompt effettivo per il canale: quello personalizzato dal proprietario se presente, altrimenti quello generato dal template."""
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    custom = settings_row.custom_voice_prompt if channel == "voice" else settings_row.custom_whatsapp_prompt
    if custom and custom.strip():
        return custom
    return await render_template_prompt(db, tenant, channel, transfer_number)
