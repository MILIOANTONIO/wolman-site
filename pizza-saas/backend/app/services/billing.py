"""
Fatturazione rigorosamente prepagata: il tenant carica credito, il canone
mensile del piano e l'uso extra (pay-as-you-go oltre i minuti inclusi) si
scalano da quel saldo - mai fattura dopo l'uso.

NESSUN pagamento reale per ora (decisione esplicita): le "ricariche" sono
simulate finché non viene collegato un vero gateway (Stripe o altro). Il
rinnovo mensile del piano è per ora un'azione manuale dell'admin: non esiste
ancora uno scheduler che lo faccia automaticamente ogni mese.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditTransaction, Tenant

PLANS = {
    "starter": {"name": "Starter", "price_cents": 9900, "included_minutes": 300, "included_numbers": 1},
    "professional": {"name": "Professional", "price_cents": 19900, "included_minutes": 700, "included_numbers": 1},
    "premium": {"name": "Premium", "price_cents": 29900, "included_minutes": 1200, "included_numbers": 1},
}

OVERAGE_CENTS_PER_MINUTE = 15


def plan_info(plan_code: str) -> dict:
    return PLANS.get(plan_code, PLANS["starter"])


async def _record_transaction(db: AsyncSession, tenant: Tenant, *, type: str, amount_cents: int, description: str) -> CreditTransaction:
    tenant.prepaid_balance_cents += amount_cents
    tx = CreditTransaction(
        tenant_id=tenant.id, type=type, amount_cents=amount_cents,
        balance_after_cents=tenant.prepaid_balance_cents, description=description,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tenant)
    return tx


async def add_credit(db: AsyncSession, tenant: Tenant, amount_cents: int, description: str = "Ricarica") -> CreditTransaction:
    if amount_cents <= 0:
        raise ValueError("L'importo della ricarica deve essere positivo")
    return await _record_transaction(db, tenant, type="topup", amount_cents=amount_cents, description=description)


async def charge_plan_renewal(db: AsyncSession, tenant: Tenant) -> CreditTransaction:
    """Addebita il canone del piano corrente e apre un nuovo periodo di utilizzo."""
    import datetime

    plan = plan_info(tenant.plan)
    tenant.current_period_minutes_used = 0
    tenant.current_period_started_at = datetime.datetime.now(datetime.timezone.utc)
    return await _record_transaction(
        db, tenant, type="plan_charge", amount_cents=-plan["price_cents"],
        description=f"Canone piano {plan['name']}",
    )


async def record_call_minutes(db: AsyncSession, tenant: Tenant, minutes: int) -> CreditTransaction | None:
    """
    Registra i minuti di una chiamata appena conclusa; se fa superare la
    soglia inclusa nel piano, addebita subito l'extra dal credito prepagato
    (solo per i minuti che eccedono la soglia in questa chiamata).
    """
    if minutes <= 0:
        return None

    plan = plan_info(tenant.plan)
    before = tenant.current_period_minutes_used
    after = before + minutes
    tenant.current_period_minutes_used = after

    overage_minutes = max(0, after - plan["included_minutes"]) - max(0, before - plan["included_minutes"])
    if overage_minutes <= 0:
        await db.commit()
        await db.refresh(tenant)
        return None

    amount_cents = -(overage_minutes * OVERAGE_CENTS_PER_MINUTE)
    return await _record_transaction(
        db, tenant, type="overage_charge", amount_cents=amount_cents,
        description=f"{overage_minutes} min extra oltre soglia piano {plan['name']}",
    )


def usage_summary(tenant: Tenant) -> dict:
    plan = plan_info(tenant.plan)
    included = plan["included_minutes"]
    used = tenant.current_period_minutes_used
    overage_minutes = max(0, used - included)
    return {
        "plan_code": tenant.plan,
        "plan_name": plan["name"],
        "plan_price_cents": plan["price_cents"],
        "included_minutes": included,
        "minutes_used": used,
        "overage_minutes": overage_minutes,
        "overage_cents_per_minute": OVERAGE_CENTS_PER_MINUTE,
        "prepaid_balance_cents": tenant.prepaid_balance_cents,
        "current_period_started_at": tenant.current_period_started_at.isoformat() if tenant.current_period_started_at else None,
    }
