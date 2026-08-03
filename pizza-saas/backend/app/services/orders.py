"""
Nucleo condiviso della pipeline ordini: sia il canale voce (tool ElevenLabs)
sia WhatsApp chiamano queste funzioni, cosi' la dashboard non deve sapere da
dove arriva un ordine.
"""
import secrets
import string
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Offering, Order, OrderItem, OrderStatusHistory
from app.routers.ws import manager as ws_manager

VALID_TRANSITIONS = {
    "ricevuto": {"in_forno", "annullato"},
    "in_forno": {"pronta", "in_consegna", "annullato"},
    "pronta": {"in_consegna", "consegnata", "annullato"},
    "in_consegna": {"consegnata", "annullato"},
    "consegnata": set(),
    "annullato": set(),
}


class OrderError(Exception):
    pass


def _order_number() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(5))


async def create_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: str,
    order_type: str,
    customer_name: str | None,
    customer_phone: str | None,
    items: list[dict],  # [{"offering_id": ..., "quantity": ..., "notes": ...}]
) -> Order:
    if not items:
        raise OrderError("L'ordine deve contenere almeno una voce")

    offering_ids = [item["offering_id"] for item in items]
    result = await db.execute(select(Offering).where(Offering.id.in_(offering_ids), Offering.tenant_id == tenant_id))
    offerings_by_id = {o.id: o for o in result.scalars().all()}

    missing = set(offering_ids) - set(offerings_by_id.keys())
    if missing:
        raise OrderError(f"Voci di menu non trovate: {missing}")

    order = Order(
        tenant_id=tenant_id,
        order_number=_order_number(),
        channel=channel,
        order_type=order_type,
        customer_name=customer_name,
        customer_phone=customer_phone,
        status="ricevuto",
        total_cents=0,
    )
    db.add(order)
    await db.flush()

    total_cents = 0
    for item in items:
        offering = offerings_by_id[item["offering_id"]]
        # Il prezzo si prende SEMPRE dal DB, mai da quanto riportato dall'AI:
        # evita che un'allucinazione del modello cambi il conto del cliente.
        quantity = max(1, int(item.get("quantity", 1)))
        line_total = offering.price_cents * quantity
        total_cents += line_total
        db.add(OrderItem(
            order_id=order.id,
            offering_id=offering.id,
            quantity=quantity,
            notes=item.get("notes"),
            price_cents_at_order=offering.price_cents,
        ))

    order.total_cents = total_cents
    db.add(OrderStatusHistory(order_id=order.id, status="ricevuto", changed_by=channel))
    await db.commit()
    await db.refresh(order)

    await ws_manager.broadcast(str(tenant_id), {
        "type": "order_created",
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "channel": order.channel,
            "order_type": order.order_type,
            "customer_name": order.customer_name,
            "status": order.status,
            "total_cents": order.total_cents,
        },
    })
    return order


async def resolve_and_create_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: str,
    order_type: str,
    customer_name: str | None,
    customer_phone: str | None,
    items_by_name: list[dict],  # [{"name": "Margherita", "quantity": 2, "notes": "..."}]
) -> Order:
    """
    Usato da entrambi i canali (tool ElevenLabs, agente WhatsApp): l'AI
    riporta i nomi dei piatti in linguaggio naturale, qui li risolviamo alle
    voci di menu reali del tenant prima di creare l'ordine - mai fidarsi di
    un id inventato dal modello.
    """
    result = await db.execute(select(Offering).where(Offering.tenant_id == tenant_id, Offering.is_available.is_(True)))
    offerings = result.scalars().all()
    by_name = {o.name.strip().lower(): o for o in offerings}

    resolved_items = []
    unmatched = []
    for item in items_by_name:
        name_key = (item.get("name") or "").strip().lower()
        offering = by_name.get(name_key)
        if not offering:
            unmatched.append(item.get("name"))
            continue
        resolved_items.append({"offering_id": offering.id, "quantity": item.get("quantity", 1), "notes": item.get("notes")})

    if unmatched:
        raise OrderError(f"Voci non trovate nel menu: {', '.join(str(u) for u in unmatched)}")

    return await create_order(
        db,
        tenant_id=tenant_id,
        channel=channel,
        order_type=order_type,
        customer_name=customer_name,
        customer_phone=customer_phone,
        items=resolved_items,
    )


async def update_order_status(db: AsyncSession, *, tenant_id: uuid.UUID, order_id: uuid.UUID, new_status: str, changed_by: str) -> Order:
    order = await db.get(Order, order_id)
    if not order or order.tenant_id != tenant_id:
        raise OrderError("Ordine non trovato")

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise OrderError(f"Transizione non valida: {order.status} -> {new_status}")

    order.status = new_status
    history = OrderStatusHistory(order_id=order.id, status=new_status, changed_by=changed_by)
    db.add(history)
    await db.commit()
    await db.refresh(order)

    await ws_manager.broadcast(str(tenant_id), {
        "type": "order_status_changed",
        "order_id": str(order.id),
        "status": new_status,
    })

    # Import qui (non in testa al file) per evitare un import circolare:
    # whatsapp_client non deve dipendere da orders.py.
    from app.services.whatsapp_client import notify_order_status
    await notify_order_status(db, order=order, history=history)

    return order
