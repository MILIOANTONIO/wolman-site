"""API della dashboard ordini del proprietario (comande in tempo reale)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_user
from app.db import get_db
from app.models import CreditTransaction, Order, OrderItem, Tenant, User
from app.services import billing
from app.services.orders import OrderError, update_order_status

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/orders")
async def list_orders(status: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Order).where(Order.tenant_id == user.tenant_id)
    if status:
        query = query.where(Order.status == status)
    result = await db.execute(query.order_by(Order.created_at.desc()).limit(200))
    orders = result.scalars().all()

    out = []
    for order in orders:
        items = (await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
        out.append({
            "id": str(order.id), "order_number": order.order_number, "channel": order.channel,
            "order_type": order.order_type, "customer_name": order.customer_name,
            "customer_phone": order.customer_phone, "status": order.status,
            "total_cents": order.total_cents, "created_at": order.created_at.isoformat(),
            "items": [{"offering_id": str(i.offering_id), "quantity": i.quantity, "notes": i.notes} for i in items],
        })
    return out


class StatusBody(BaseModel):
    status: str


@router.post("/orders/{order_id}/status")
async def set_order_status(order_id: uuid.UUID, body: StatusBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        order = await update_order_status(db, tenant_id=user.tenant_id, order_id=order_id, new_status=body.status, changed_by=user.email)
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "status": order.status}


@router.get("/billing")
async def get_billing(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
async def topup_balance(body: TopupBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
async def get_plans_dashboard(user: User = Depends(get_current_user)):
    return billing.PLANS
