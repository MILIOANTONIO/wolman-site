"""
Automazione sospensione/cancellazione per mancato pagamento (piattaforma
rigorosamente prepagata, vedi services/billing.py): se il rinnovo mensile
fallisce per credito insufficiente, il tenant passa a "past_due"; dopo un
periodo di grazia configurabile viene sospeso (WhatsApp bloccato, agente
vocale sostituito con un messaggio di cortesia); dopo un ulteriore periodo
il numero viene rilasciato per davvero su DIDWW (azione irreversibile).

Tutto e' gestito da un ciclo periodico avviato in app/main.py, spento con
un solo interruttore (PlatformSettings.auto_enforcement_enabled) - pensato
per essere disattivabile subito se qualcosa non torna, senza dover fermare
il server.
"""
import datetime
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DidwwRegulatoryProfile, PhoneNumber, PlatformSettings, Tenant, User
from app.services import billing, didww_client
from app.services.elevenlabs_agents import assign_phone_number, delete_phone_number
from app.services.resend_email import send_email


async def get_or_create_settings(db: AsyncSession) -> PlatformSettings:
    settings = (await db.execute(select(PlatformSettings))).scalars().first()
    if not settings:
        settings = PlatformSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def _owner_email(db: AsyncSession, tenant_id) -> str | None:
    owner = (await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == "owner"))).scalars().first()
    return owner.email if owner else None


async def _notify(db: AsyncSession, tenant: Tenant, subject: str, body: str) -> None:
    email = await _owner_email(db, tenant.id)
    if not email:
        return
    try:
        await send_email(email, subject, body)
    except Exception as e:
        sys.stderr.write(f"Notifica fatturazione fallita per tenant {tenant.id}: {e}\n")


async def _suspend_tenant(db: AsyncSession, tenant: Tenant) -> None:
    tenant.billing_status = "suspended"
    tenant.suspended_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    numbers = (
        await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant.id, PhoneNumber.status == "active"))
    ).scalars().all()
    for n in numbers:
        n.status = "suspended"
        # Scollega il numero dall'agente su ElevenLabs: le chiamate non
        # arrivano piu' a nessun agente, non e' solo un messaggio diverso -
        # sospensione vera, senza cancellare il numero su DIDWW.
        if n.elevenlabs_phone_number_id:
            try:
                await assign_phone_number(n.elevenlabs_phone_number_id, None)
            except Exception as e:
                sys.stderr.write(f"Sospensione numero ElevenLabs fallita per {n.e164_number} (tenant {tenant.id}): {e}\n")
    await db.commit()

    await _notify(
        db, tenant, f"Servizio sospeso — {tenant.business_name}",
        "Il credito prepagato non è sufficiente per il rinnovo del piano e il periodo di grazia è scaduto.\n"
        "Il tuo agente AI e il numero sono stati sospesi. Ricarica il credito dalla dashboard per riattivarli subito.",
    )


async def _terminate_tenant_numbers(db: AsyncSession, tenant: Tenant) -> None:
    numbers = (
        await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant.id, PhoneNumber.status == "suspended"))
    ).scalars().all()
    for n in numbers:
        if n.didww_reference:
            try:
                await didww_client.terminate_did(n.didww_reference)
            except Exception as e:
                sys.stderr.write(f"Cancellazione DIDWW fallita per numero {n.e164_number} (tenant {tenant.id}): {e}\n")
                continue
        if n.elevenlabs_phone_number_id:
            try:
                await delete_phone_number(n.elevenlabs_phone_number_id)
            except Exception as e:
                sys.stderr.write(f"Cancellazione numero ElevenLabs fallita per {n.e164_number} (tenant {tenant.id}): {e}\n")
        n.status = "terminated"

    profile = (await db.execute(select(DidwwRegulatoryProfile).where(DidwwRegulatoryProfile.tenant_id == tenant.id))).scalar_one_or_none()
    if profile:
        profile.activation_status = "scaduto"
    await db.commit()

    await _notify(
        db, tenant, f"Numero rilasciato — {tenant.business_name}",
        "Il numero di telefono non è stato rinnovato per oltre il periodo massimo consentito ed è stato rilasciato. "
        "Ricarica il credito e prenota un nuovo numero dalla dashboard per tornare operativo.",
    )


async def reactivate_tenant_if_paid(db: AsyncSession, tenant: Tenant) -> None:
    """Chiamata da billing.add_credit dopo ogni ricarica: se il tenant era
    in past_due/suspended e ora il saldo copre il piano, lo riattiva subito
    invece di aspettare il prossimo ciclo periodico."""
    if tenant.billing_status not in ("past_due", "suspended"):
        return
    plan = billing.plan_info(tenant.plan)
    if tenant.prepaid_balance_cents < plan["price_cents"]:
        return

    was_suspended = tenant.billing_status == "suspended"
    tenant.billing_status = "active"
    tenant.past_due_since = None
    tenant.suspended_at = None
    await db.commit()

    if not was_suspended:
        return

    numbers = (
        await db.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant.id, PhoneNumber.status == "suspended"))
    ).scalars().all()
    for n in numbers:
        n.status = "active"
        if n.elevenlabs_phone_number_id:
            try:
                await assign_phone_number(n.elevenlabs_phone_number_id, tenant.elevenlabs_agent_id)
            except Exception as e:
                sys.stderr.write(f"Riattivazione numero ElevenLabs fallita per {n.e164_number} (tenant {tenant.id}): {e}\n")
    await db.commit()

    await _notify(
        db, tenant, f"Servizio riattivato — {tenant.business_name}",
        "Il credito è stato ricaricato: il tuo agente AI e il numero sono di nuovo attivi.",
    )


async def run_enforcement_cycle(db: AsyncSession) -> None:
    settings = await get_or_create_settings(db)
    if not settings.auto_enforcement_enabled:
        return

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Rinnovo mensile: solo tenant attivati (numero+agente gia' provisionati).
    renewal_due = (
        await db.execute(
            select(Tenant).where(
                Tenant.status == "active",
                Tenant.billing_status.in_(["trial", "active"]),
            )
        )
    ).scalars().all()
    for tenant in renewal_due:
        if tenant.current_period_started_at and (now - tenant.current_period_started_at) < datetime.timedelta(days=30):
            continue
        plan = billing.plan_info(tenant.plan)
        if tenant.prepaid_balance_cents >= plan["price_cents"]:
            await billing.charge_plan_renewal(db, tenant)
            tenant.billing_status = "active"
            await db.commit()
        else:
            if tenant.billing_status != "past_due":
                tenant.billing_status = "past_due"
                tenant.past_due_since = now
                await db.commit()
                await _notify(
                    db, tenant, f"Credito insufficiente per il rinnovo — {tenant.business_name}",
                    f"Il rinnovo del piano non è andato a buon fine per credito insufficiente. "
                    f"Ricarica entro {settings.suspend_grace_days} giorni per evitare la sospensione del servizio.",
                )

    # 2. Sospensione dopo il periodo di grazia.
    past_due = (
        await db.execute(select(Tenant).where(Tenant.billing_status == "past_due", Tenant.past_due_since.is_not(None)))
    ).scalars().all()
    for tenant in past_due:
        if (now - tenant.past_due_since) >= datetime.timedelta(days=settings.suspend_grace_days):
            await _suspend_tenant(db, tenant)

    # 3. Cancellazione definitiva del numero dopo il periodo massimo da sospeso.
    suspended = (
        await db.execute(select(Tenant).where(Tenant.billing_status == "suspended", Tenant.suspended_at.is_not(None)))
    ).scalars().all()
    for tenant in suspended:
        if (now - tenant.suspended_at) >= datetime.timedelta(days=settings.terminate_after_days):
            await _terminate_tenant_numbers(db, tenant)
