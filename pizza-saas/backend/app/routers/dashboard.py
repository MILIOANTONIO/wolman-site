"""API della dashboard ordini del proprietario (comande in tempo reale)."""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import sys

from app.auth.session import get_current_owner, require_roles
from app.db import get_db
from app.models import CreditTransaction, Offering, Order, OrderItem, Reservation, Tenant, TenantSettings, User
from app.services import billing
from app.services.elevenlabs_agents import create_agent, update_agent
from app.services.orders import OrderError, claim_available_orders, update_order_status, update_reservation_status
from app.services.prompt_builder import build_agent_prompt, render_template_prompt

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Ordini: visibili a chi li prepara (cuoco) e a chi consegna (delivery),
# oltre al titolare. Il ruolo "delivery" vede solo gli ordini a domicilio
# (non ha senso che gestisca l'asporto).
_ORDERS_ROLES = require_roles("owner", "cuoco", "delivery")
_RESERVATIONS_ROLES = require_roles("owner", "receptionista")


@router.get("/orders")
async def list_orders(status: str | None = None, user: User = Depends(_ORDERS_ROLES), db: AsyncSession = Depends(get_db)):
    query = select(Order).where(Order.tenant_id == user.tenant_id)
    if user.role == "delivery":
        # Ogni fattorino vede solo le consegne assegnate a lui (vedi
        # auto_assign_order/claim_available_orders in services/orders.py) -
        # non tutte le consegne del tenant, altrimenti con piu' fattorini
        # vedrebbero tutti lo stesso elenco.
        query = query.where(Order.order_type == "delivery", Order.assigned_to_user_id == user.id)
    if status:
        query = query.where(Order.status == status)
    result = await db.execute(query.order_by(Order.created_at.desc()).limit(200))
    orders = result.scalars().all()

    assigned_ids = {o.assigned_to_user_id for o in orders if o.assigned_to_user_id}
    emails_by_id = {}
    if assigned_ids and user.role != "delivery":
        rows = (await db.execute(select(User.id, User.email).where(User.id.in_(assigned_ids)))).all()
        emails_by_id = {uid: email for uid, email in rows}

    out = []
    for order in orders:
        rows = (
            await db.execute(
                select(OrderItem, Offering.name)
                .join(Offering, Offering.id == OrderItem.offering_id)
                .where(OrderItem.order_id == order.id)
            )
        ).all()
        out.append({
            "id": str(order.id), "order_number": order.order_number, "channel": order.channel,
            "order_type": order.order_type, "customer_name": order.customer_name,
            "customer_phone": order.customer_phone, "status": order.status,
            "total_cents": order.total_cents, "created_at": order.created_at.isoformat(),
            "delivery_address": order.delivery_address, "delivery_lat": order.delivery_lat, "delivery_lng": order.delivery_lng,
            "assigned_to_user_id": str(order.assigned_to_user_id) if order.assigned_to_user_id else None,
            "assigned_to_email": emails_by_id.get(order.assigned_to_user_id),
            "items": [{"name": name, "quantity": i.quantity, "notes": i.notes} for i, name in rows],
        })
    return out


class StatusBody(BaseModel):
    status: str


@router.post("/orders/{order_id}/status")
async def set_order_status(order_id: uuid.UUID, body: StatusBody, user: User = Depends(_ORDERS_ROLES), db: AsyncSession = Depends(get_db)):
    try:
        order = await update_order_status(db, tenant_id=user.tenant_id, order_id=order_id, new_status=body.status, changed_by=user.email)
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "status": order.status}


@router.get("/billing")
async def get_billing(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, user.tenant_id)
    result = await db.execute(
        select(CreditTransaction).where(CreditTransaction.tenant_id == user.tenant_id).order_by(CreditTransaction.created_at.desc()).limit(100)
    )
    transactions = [
        {
            "id": str(t.id), "type": t.type, "amount_cents": t.amount_cents,
            "balance_after_cents": t.balance_after_cents, "description": t.description,
            "created_at": t.created_at.isoformat(),
        }
        for t in result.scalars().all()
    ]
    return {**billing.usage_summary(tenant), "transactions": transactions}


class TopupBody(BaseModel):
    amount_cents: int


@router.post("/billing/topup")
async def topup_balance(body: TopupBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    # SIMULATO: nessun pagamento reale, il saldo viene semplicemente
    # incrementato - da collegare a un vero gateway di pagamento prima di
    # usarlo con clienti veri.
    tenant = await db.get(Tenant, user.tenant_id)
    try:
        await billing.add_credit(db, tenant, body.amount_cents, description="Ricarica (simulata)")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "prepaid_balance_cents": tenant.prepaid_balance_cents}


@router.get("/plans")
async def get_plans_dashboard(user: User = Depends(get_current_owner)):
    return billing.PLANS


@router.get("/agent-prompt")
async def get_agent_prompt(channel: str = "voice", user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    """Prompt reale usato dall'AI: personalizzato se il proprietario lo ha modificato, altrimenti generato da menu/orari/impostazioni."""
    if channel not in ("voice", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canale non valido")
    tenant = await db.get(Tenant, user.tenant_id)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    is_custom = bool(settings_row.custom_voice_prompt if channel == "voice" else settings_row.custom_whatsapp_prompt)
    prompt = await build_agent_prompt(db, tenant, channel=channel)
    return {"channel": channel, "prompt": prompt, "is_custom": is_custom, "elevenlabs_agent_id": tenant.elevenlabs_agent_id}


class AgentPromptBody(BaseModel):
    channel: str
    prompt: str


@router.put("/agent-prompt")
async def set_agent_prompt(body: AgentPromptBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    if body.channel not in ("voice", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canale non valido")

    tenant = await db.get(Tenant, user.tenant_id)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()

    if body.channel == "voice":
        settings_row.custom_voice_prompt = body.prompt
    else:
        settings_row.custom_whatsapp_prompt = body.prompt
    await db.commit()

    pushed_to_elevenlabs = False
    if body.channel == "voice" and tenant.elevenlabs_agent_id:
        # L'agente esiste già (tenant approvato): aggiorniamo subito
        # ElevenLabs, non serve aspettare una nuova approvazione admin.
        try:
            first_message = f"Ciao, grazie per aver chiamato {tenant.business_name}! Come posso aiutarti?"
            await update_agent(
                tenant.elevenlabs_agent_id, name=f"{tenant.business_name} - {settings_row.agent_persona_name}",
                prompt=body.prompt, first_message=first_message, voice_id=settings_row.agent_voice_id,
            )
            pushed_to_elevenlabs = True
        except Exception as e:
            sys.stderr.write(f"Aggiornamento prompt su ElevenLabs fallito per tenant {user.tenant_id}: {e}\n")
            raise HTTPException(status_code=502, detail="Prompt salvato, ma l'aggiornamento su ElevenLabs è fallito - riprova")

    return {"ok": True, "pushed_to_elevenlabs": pushed_to_elevenlabs}


@router.post("/agent-prompt/reset")
async def reset_agent_prompt(channel: str = "voice", user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    """Torna al prompt generato automaticamente da menu/orari/impostazioni, scartando la personalizzazione."""
    if channel not in ("voice", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canale non valido")

    tenant = await db.get(Tenant, user.tenant_id)
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant.id))).scalar_one()
    if channel == "voice":
        settings_row.custom_voice_prompt = None
    else:
        settings_row.custom_whatsapp_prompt = None
    await db.commit()

    prompt = await render_template_prompt(db, tenant, channel=channel)
    return {"ok": True, "prompt": prompt}


@router.get("/stats")
async def get_owner_stats(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    total_orders = (
        await db.execute(select(func.count()).select_from(Order).where(Order.tenant_id == user.tenant_id))
    ).scalar_one()
    total_revenue_cents = (
        await db.execute(select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.tenant_id == user.tenant_id))
    ).scalar_one()
    orders_by_status = dict(
        (await db.execute(
            select(Order.status, func.count()).where(Order.tenant_id == user.tenant_id).group_by(Order.status)
        )).all()
    )
    orders_by_channel = dict(
        (await db.execute(
            select(Order.channel, func.count()).where(Order.tenant_id == user.tenant_id).group_by(Order.channel)
        )).all()
    )

    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=13)
    day = func.date(Order.created_at)
    daily_rows = (
        await db.execute(
            select(day.label("day"), func.count().label("orders"), func.coalesce(func.sum(Order.total_cents), 0).label("revenue_cents"))
            .where(Order.tenant_id == user.tenant_id, Order.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
    ).all()
    daily_by_date = {str(row.day): {"orders": row.orders, "revenue_cents": row.revenue_cents} for row in daily_rows}
    daily_series = []
    for i in range(14):
        d = (since + datetime.timedelta(days=i)).date()
        entry = daily_by_date.get(str(d), {"orders": 0, "revenue_cents": 0})
        daily_series.append({"date": str(d), "orders": entry["orders"], "revenue_cents": entry["revenue_cents"]})

    return {
        "total_orders": total_orders,
        "total_revenue_cents": total_revenue_cents,
        "orders_by_status": orders_by_status,
        "orders_by_channel": orders_by_channel,
        "daily_last_14_days": daily_series,
    }


@router.get("/reservations")
async def list_reservations(user: User = Depends(_RESERVATIONS_ROLES), db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == user.tenant_id))).scalar_one()

    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    rows = (
        await db.execute(
            select(Reservation)
            .where(Reservation.tenant_id == user.tenant_id, Reservation.starts_at >= since, Reservation.starts_at <= until)
            .order_by(Reservation.starts_at)
        )
    ).scalars().all()

    return {
        "table_capacity": settings_row.table_capacity or {},
        "reservations": [
            {
                "id": str(r.id), "customer_name": r.customer_name, "customer_phone": r.customer_phone,
                "party_size": r.party_size, "starts_at": r.starts_at.isoformat(), "status": r.status, "notes": r.notes,
            }
            for r in rows
        ],
    }


class ReservationStatusBody(BaseModel):
    status: str  # confermata, annullata, completata, no_show


@router.post("/reservations/{reservation_id}/status")
async def set_reservation_status(reservation_id: uuid.UUID, body: ReservationStatusBody, user: User = Depends(_RESERVATIONS_ROLES), db: AsyncSession = Depends(get_db)):
    try:
        reservation = await update_reservation_status(db, tenant_id=user.tenant_id, reservation_id=reservation_id, new_status=body.status)
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "status": reservation.status}


# Tracciamento posizione fattorini: il sotto-account "delivery" manda la
# propria posizione GPS dal browser del telefono ogni pochi secondi mentre
# ha una consegna attiva; il titolare vede tutti i fattorini attivi su una
# mappa. Solo l'ultima posizione nota viene tenuta (niente storico tragitto).
_DELIVERY_ONLINE_MINUTES = 10


class DeliveryLocationBody(BaseModel):
    lat: float
    lng: float


@router.put("/delivery/location")
async def update_delivery_location(body: DeliveryLocationBody, user: User = Depends(require_roles("delivery")), db: AsyncSession = Depends(get_db)):
    user.current_lat = body.lat
    user.current_lng = body.lng
    user.location_updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    from app.routers.ws import manager as ws_manager
    await ws_manager.broadcast(str(user.tenant_id), {
        "type": "delivery_location_changed",
        "user_id": str(user.id),
        "email": user.email,
        "lat": body.lat,
        "lng": body.lng,
    })
    return {"ok": True}


class DutyBody(BaseModel):
    on_duty: bool


@router.put("/delivery/duty")
async def set_duty(body: DutyBody, user: User = Depends(require_roles("delivery")), db: AsyncSession = Depends(get_db)):
    user.on_duty = body.on_duty
    await db.commit()

    claimed = 0
    if body.on_duty:
        claimed = await claim_available_orders(db, tenant_id=user.tenant_id, rider=user)

    return {"ok": True, "on_duty": user.on_duty, "claimed_orders": claimed}


@router.get("/delivery/locations")
async def list_delivery_locations(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=_DELIVERY_ONLINE_MINUTES)
    rows = (
        await db.execute(
            select(User).where(
                User.tenant_id == user.tenant_id, User.role == "delivery",
                User.location_updated_at.is_not(None), User.location_updated_at >= since,
            )
        )
    ).scalars().all()
    return [
        {
            "user_id": str(u.id), "email": u.email, "lat": u.current_lat, "lng": u.current_lng,
            "updated_at": u.location_updated_at.isoformat(), "on_duty": u.on_duty,
        }
        for u in rows
    ]


_ANY_TEAM_ROLE = require_roles("owner", "cuoco", "receptionista", "delivery")
_ONLINE_WITHIN_MINUTES = 3
_ROLE_LABELS = {"owner": "Titolare", "cuoco": "Cuoco/pizzaiolo", "receptionista": "Receptionist", "delivery": "Delivery"}


@router.get("/team-presence")
async def team_presence(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(User).where(User.tenant_id == user.tenant_id).order_by(User.role, User.created_at))
    ).scalars().all()
    now = datetime.datetime.now(datetime.timezone.utc)
    return [
        {
            "id": str(u.id), "email": u.email, "role": u.role, "role_label": _ROLE_LABELS.get(u.role, u.role),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
            "online": bool(u.last_seen_at and (now - u.last_seen_at) <= datetime.timedelta(minutes=_ONLINE_WITHIN_MINUTES)),
            "on_duty": u.on_duty if u.role == "delivery" else None,
        }
        for u in rows
    ]


@router.put("/heartbeat")
async def heartbeat(user: User = Depends(_ANY_TEAM_ROLE), db: AsyncSession = Depends(get_db)):
    """Chiamato dal frontend ogni minuto mentre la dashboard e' aperta (vedi
    dashboard/layout.tsx), per sapere chi e' online in questo momento - non
    serve nient'altro lato client, e' solo un timestamp."""
    user.last_seen_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return {"ok": True}
