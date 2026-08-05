"""
Nucleo condiviso della pipeline ordini: sia il canale voce (tool ElevenLabs)
sia WhatsApp chiamano queste funzioni, cosi' la dashboard non deve sapere da
dove arriva un ordine.
"""
import datetime
import math
import secrets
import string
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Offering, Order, OrderItem, OrderStatusHistory, Promotion, Reservation, Tenant, TenantSettings, User
from app.routers.ws import manager as ws_manager

VALID_TRANSITIONS = {
    "ricevuto": {"in_forno", "annullato"},
    "in_forno": {"pronta", "in_consegna", "annullato"},
    "pronta": {"in_consegna", "consegnata", "annullato"},
    "in_consegna": {"consegnata", "annullato"},
    "consegnata": set(),
    "annullato": set(),
}

VALID_RESERVATION_TRANSITIONS = {
    "richiesta": {"confermata", "annullata"},
    "confermata": {"completata", "no_show", "annullata"},
    "completata": set(),
    "no_show": set(),
    "annullata": set(),
}


class OrderError(Exception):
    pass


def _order_number() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(5))


_DAY_KEYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]  # datetime.weekday(): 0=lunedi...6=domenica, stesso ordine


def _promo_active_now(promo: Promotion, *, tenant_timezone: str) -> bool:
    now = datetime.datetime.now(ZoneInfo(tenant_timezone or "Europe/Rome"))
    day_cfg = (promo.schedule or {}).get(_DAY_KEYS[now.weekday()])
    if not day_cfg or not day_cfg.get("enabled"):
        return False
    frm, to = day_cfg.get("from"), day_cfg.get("to")
    if not frm or not to:
        return True  # nessun orario specificato = valida tutto il giorno
    return frm <= now.strftime("%H:%M") <= to


def _buy_x_get_y_discount(promo: Promotion, eligible: list[dict]) -> int:
    """'Paghi buy_qty, ricevi get_qty': ogni get_qty unità dello stesso
    gruppo, le (get_qty - buy_qty) più economiche sono in omaggio."""
    if not promo.buy_qty or not promo.get_qty or promo.get_qty <= promo.buy_qty:
        return 0
    unit_prices = []
    for it in eligible:
        unit_prices.extend([it["offering"].price_cents] * it["quantity"])
    if len(unit_prices) < promo.get_qty:
        return 0
    unit_prices.sort(reverse=True)
    free_per_group = promo.get_qty - promo.buy_qty
    discount = 0
    for i in range(0, len(unit_prices) - len(unit_prices) % promo.get_qty, promo.get_qty):
        group = sorted(unit_prices[i:i + promo.get_qty])
        discount += sum(group[:free_per_group])
    return discount


def _promo_discount_cents(promo: Promotion, items_with_offering: list[dict], order_subtotal_cents: int) -> int:
    if promo.min_order_cents and order_subtotal_cents < promo.min_order_cents:
        return 0
    eligible = [it for it in items_with_offering if not promo.applies_to_group or it["offering"].group_name == promo.applies_to_group]
    if not eligible:
        return 0
    if promo.promo_type == "buy_x_get_y":
        return _buy_x_get_y_discount(promo, eligible)
    eligible_subtotal = sum(it["offering"].price_cents * it["quantity"] for it in eligible)
    if promo.promo_type == "percent_discount":
        return round(eligible_subtotal * (promo.discount_percent or 0) / 100)
    if promo.promo_type == "fixed_discount":
        return min(promo.discount_cents or 0, eligible_subtotal)
    return 0


async def _best_active_promotion(
    db: AsyncSession, *, tenant_id: uuid.UUID, tenant_timezone: str, items_with_offering: list[dict], order_subtotal_cents: int
) -> tuple[Promotion, int] | None:
    """Tra le promozioni attive in questo momento, applica quella che fa
    risparmiare di più al cliente - niente combinazione tra più promozioni,
    per restare prevedibile sia per il titolare sia per l'agente AI."""
    promos = (await db.execute(select(Promotion).where(Promotion.tenant_id == tenant_id, Promotion.is_active.is_(True)))).scalars().all()
    best: tuple[Promotion, int] | None = None
    for promo in promos:
        if not _promo_active_now(promo, tenant_timezone=tenant_timezone):
            continue
        discount = _promo_discount_cents(promo, items_with_offering, order_subtotal_cents)
        if discount > 0 and (best is None or discount > best[1]):
            best = (promo, discount)
    return best


async def create_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: str,
    order_type: str,
    customer_name: str | None,
    customer_phone: str | None,
    items: list[dict],  # [{"offering_id": ..., "quantity": ..., "notes": ...}]
    delivery_address: str | None = None,
) -> Order:
    if not items:
        raise OrderError("L'ordine deve contenere almeno una voce")

    offering_ids = [item["offering_id"] for item in items]
    result = await db.execute(select(Offering).where(Offering.id.in_(offering_ids), Offering.tenant_id == tenant_id))
    offerings_by_id = {o.id: o for o in result.scalars().all()}

    missing = set(offering_ids) - set(offerings_by_id.keys())
    if missing:
        raise OrderError(f"Voci di menu non trovate: {missing}")

    tenant = await db.get(Tenant, tenant_id)

    delivery_lat = delivery_lng = None
    if order_type == "delivery" and delivery_address:
        from app.services.geocoding import geocode_address
        coords = await geocode_address(delivery_address, region_hint="it")
        if coords:
            delivery_lat, delivery_lng = coords

    order = Order(
        tenant_id=tenant_id,
        order_number=_order_number(),
        channel=channel,
        order_type=order_type,
        customer_name=customer_name,
        customer_phone=customer_phone,
        status="ricevuto",
        total_cents=0,
        delivery_address=delivery_address,
        delivery_lat=delivery_lat,
        delivery_lng=delivery_lng,
    )
    db.add(order)
    await db.flush()

    total_cents = 0
    items_with_offering = []
    for item in items:
        offering = offerings_by_id[item["offering_id"]]
        # Il prezzo si prende SEMPRE dal DB, mai da quanto riportato dall'AI:
        # evita che un'allucinazione del modello cambi il conto del cliente.
        quantity = max(1, int(item.get("quantity", 1)))
        line_total = offering.price_cents * quantity
        total_cents += line_total
        items_with_offering.append({"offering": offering, "quantity": quantity})
        db.add(OrderItem(
            order_id=order.id,
            offering_id=offering.id,
            quantity=quantity,
            notes=item.get("notes"),
            price_cents_at_order=offering.price_cents,
        ))

    # Promozioni: ricalcolate qui, mai fidandosi di quanto detto dall'AI al
    # cliente - stessa logica del prezzo dei singoli piatti sopra.
    best_promo = await _best_active_promotion(
        db, tenant_id=tenant_id, tenant_timezone=tenant.timezone if tenant else "Europe/Rome",
        items_with_offering=items_with_offering, order_subtotal_cents=total_cents,
    )
    discount_cents = best_promo[1] if best_promo else 0

    delivery_fee_cents = 0
    if order_type == "delivery":
        settings_row = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))).scalar_one_or_none()
        delivery_fee_cents = settings_row.delivery_fee_cents if settings_row else 0

    order.total_cents = max(0, total_cents - discount_cents) + delivery_fee_cents
    order.discount_cents = discount_cents
    order.applied_promotion_title = best_promo[0].title if best_promo else None
    order.delivery_fee_cents = delivery_fee_cents
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
            "discount_cents": order.discount_cents,
            "applied_promotion_title": order.applied_promotion_title,
            "delivery_fee_cents": order.delivery_fee_cents,
        },
    })

    from app.services.push import send_push_to_roles
    await send_push_to_roles(
        db, tenant_id=tenant_id, roles=["owner", "cuoco"],
        title=f"Nuovo ordine #{order.order_number}",
        body=f"{order.customer_name or 'Cliente'} — {order.order_type} — {total_cents / 100:.2f} €",
        url="/dashboard",
    )
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
    delivery_address: str | None = None,
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
        delivery_address=delivery_address,
    )


async def create_reservation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    channel: str,
    customer_name: str,
    customer_phone: str | None,
    party_size: int | None,
    date: str,  # "AAAA-MM-GG"
    time: str,  # "HH:MM"
    notes: str | None,
) -> Reservation:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise OrderError("Pizzeria non trovata")

    try:
        naive = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise OrderError("Data o ora della prenotazione non valida")

    tz = ZoneInfo(tenant.timezone or "Europe/Rome")
    starts_at = naive.replace(tzinfo=tz).astimezone(datetime.timezone.utc)

    reservation = Reservation(
        tenant_id=tenant_id,
        channel=channel,
        customer_name=customer_name,
        customer_phone=customer_phone,
        party_size=party_size,
        starts_at=starts_at,
        status="richiesta",
        notes=notes,
    )
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)

    await ws_manager.broadcast(str(tenant_id), {
        "type": "reservation_created",
        "reservation": {
            "id": str(reservation.id),
            "customer_name": reservation.customer_name,
            "customer_phone": reservation.customer_phone,
            "party_size": reservation.party_size,
            "starts_at": reservation.starts_at.isoformat(),
            "status": reservation.status,
        },
    })

    from app.services.push import send_push_to_roles
    await send_push_to_roles(
        db, tenant_id=tenant_id, roles=["owner", "receptionista"],
        title="Nuova prenotazione",
        body=f"{customer_name} — {party_size or '?'} persone — {date} {time}",
        url="/dashboard/prenotazioni",
    )
    return reservation


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def _pick_best_rider(db: AsyncSession, *, tenant_id: uuid.UUID, order: Order) -> User | None:
    """
    Sceglie il fattorino a cui assegnare un ordine "pronta": tra quelli in
    servizio, preferisce chi ha meno consegne attive in questo momento
    (carico di lavoro) - a parita' di carico, il piu' vicino all'indirizzo
    di consegna (se abbiamo le coordinate di entrambi). Chi e' gia' impegnato
    in una consegna viene naturalmente scavalcato perche' ha piu' carico.
    """
    riders = (
        await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == "delivery", User.on_duty.is_(True)))
    ).scalars().all()
    if not riders:
        return None
    if len(riders) == 1:
        return riders[0]

    load_rows = (
        await db.execute(
            select(Order.assigned_to_user_id)
            .where(Order.tenant_id == tenant_id, Order.status.in_(["pronta", "in_consegna"]), Order.assigned_to_user_id.is_not(None))
        )
    ).all()
    load_by_rider: dict[uuid.UUID, int] = {}
    for (rider_id,) in load_rows:
        load_by_rider[rider_id] = load_by_rider.get(rider_id, 0) + 1

    def sort_key(rider: User):
        load = load_by_rider.get(rider.id, 0)
        if order.delivery_lat is not None and order.delivery_lng is not None and rider.current_lat is not None and rider.current_lng is not None:
            distance = _distance_km(order.delivery_lat, order.delivery_lng, rider.current_lat, rider.current_lng)
        else:
            distance = float("inf")
        return (load, distance)

    return sorted(riders, key=sort_key)[0]


async def auto_assign_order(db: AsyncSession, *, tenant_id: uuid.UUID, order: Order) -> None:
    if order.order_type != "delivery" or order.assigned_to_user_id is not None:
        return
    rider = await _pick_best_rider(db, tenant_id=tenant_id, order=order)
    if not rider:
        return
    order.assigned_to_user_id = rider.id
    await db.commit()

    await ws_manager.broadcast(str(tenant_id), {
        "type": "order_assigned", "order_id": str(order.id), "assigned_to_user_id": str(rider.id),
    })
    from app.services.push import send_push_to_users
    await send_push_to_users(
        db, user_ids=[rider.id],
        title=f"Ordine #{order.order_number} da consegnare",
        body=f"{order.customer_name or 'Cliente'} — {order.delivery_address or ''}",
        url="/dashboard",
    )


async def claim_available_orders(db: AsyncSession, *, tenant_id: uuid.UUID, rider: User) -> int:
    """Chiamata quando un fattorino si mette "in servizio": recupera gli
    ordini "pronta" senza fattorino assegnato (es. perche' prima non c'era
    nessuno in servizio)."""
    orders = (
        await db.execute(
            select(Order).where(
                Order.tenant_id == tenant_id, Order.order_type == "delivery",
                Order.status == "pronta", Order.assigned_to_user_id.is_(None),
            )
        )
    ).scalars().all()
    for order in orders:
        order.assigned_to_user_id = rider.id
    if orders:
        await db.commit()
        for order in orders:
            await ws_manager.broadcast(str(tenant_id), {
                "type": "order_assigned", "order_id": str(order.id), "assigned_to_user_id": str(rider.id),
            })
    return len(orders)


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

    if new_status == "pronta" and order.order_type == "delivery":
        await auto_assign_order(db, tenant_id=tenant_id, order=order)

    if new_status == "in_consegna" and order.order_type == "delivery":
        from app.services.push import send_push_to_roles
        await send_push_to_roles(
            db, tenant_id=tenant_id, roles=["owner", "delivery"],
            title=f"Ordine #{order.order_number} pronto per la consegna",
            body=f"{order.customer_name or 'Cliente'} — {order.total_cents / 100:.2f} €",
            url="/dashboard",
        )

    return order


async def update_reservation_status(db: AsyncSession, *, tenant_id: uuid.UUID, reservation_id: uuid.UUID, new_status: str) -> Reservation:
    reservation = await db.get(Reservation, reservation_id)
    if not reservation or reservation.tenant_id != tenant_id:
        raise OrderError("Prenotazione non trovata")

    allowed = VALID_RESERVATION_TRANSITIONS.get(reservation.status, set())
    if new_status not in allowed:
        raise OrderError(f"Transizione non valida: {reservation.status} -> {new_status}")

    reservation.status = new_status
    await db.commit()
    await db.refresh(reservation)

    await ws_manager.broadcast(str(tenant_id), {
        "type": "reservation_status_changed",
        "reservation_id": str(reservation.id),
        "status": new_status,
    })
    return reservation
