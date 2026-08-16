"""
Sotto-account del tenant: il titolare (owner) può creare accessi separati e
limitati per il personale - cuoco/pizzaiolo (comande in cucina), receptionista
(prenotazioni tavoli), delivery (consegne). Ogni sotto-account è un User con
lo stesso tenant_id del titolare ma un role diverso da "owner"; l'accesso
alle sezioni della dashboard è ristretto lato backend in base a quel role
(vedi require_roles in app/auth/session.py), non solo nascosto in UI.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_owner
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/team", tags=["team"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SUB_ROLES = {"cuoco", "receptionista", "delivery"}
ROLE_LABELS = {"cuoco": "Cuoco/pizzaiolo", "receptionista": "Receptionist", "delivery": "Delivery"}


@router.get("")
async def list_team(user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(User).where(User.tenant_id == user.tenant_id, User.role != "owner").order_by(User.created_at))
    ).scalars().all()
    return [{"id": str(m.id), "email": m.email, "role": m.role, "role_label": ROLE_LABELS.get(m.role, m.role)} for m in rows]


class TeamMemberBody(BaseModel):
    email: EmailStr
    password: str
    role: str


@router.post("")
async def create_team_member(body: TeamMemberBody, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    if body.role not in SUB_ROLES:
        raise HTTPException(status_code=400, detail="Ruolo non valido")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="La password deve avere almeno 8 caratteri")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email già registrata")

    member = User(tenant_id=user.tenant_id, email=body.email, password_hash=pwd_context.hash(body.password), role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return {"id": str(member.id), "email": member.email, "role": member.role, "role_label": ROLE_LABELS.get(member.role, member.role)}


@router.delete("/{member_id}")
async def delete_team_member(member_id: uuid.UUID, user: User = Depends(get_current_owner), db: AsyncSession = Depends(get_db)):
    member = await db.get(User, member_id)
    if not member or member.tenant_id != user.tenant_id or member.role == "owner":
        raise HTTPException(status_code=404, detail="Non trovato")
    await db.delete(member)
    await db.commit()
    return {"ok": True}
