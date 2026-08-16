"""Signup/login via email+password, logout, e /me - alternativa a Google."""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import User, clear_session_cookie, get_current_user, issue_session_cookie
from app.db import get_db
from app.models import Tenant, TenantSettings

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SignupBody(BaseModel):
    email: EmailStr
    password: str
    business_name: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
async def signup(body: SignupBody, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email già registrata")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="La password deve avere almeno 8 caratteri")

    tenant = Tenant(business_name=body.business_name, slug=f"{body.business_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}", status="pending_kyc")
    db.add(tenant)
    await db.flush()
    db.add(TenantSettings(tenant_id=tenant.id))

    user = User(tenant_id=tenant.id, email=body.email, password_hash=pwd_context.hash(body.password), role="owner")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    issue_session_cookie(response, sub=str(user.id), role="owner", tenant_id=str(user.tenant_id))
    return {"ok": True}


@router.post("/login")
async def login(body: LoginBody, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o password errati")

    user.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    user.last_seen_at = user.last_login_at
    await db.commit()

    issue_session_cookie(response, sub=str(user.id), role="owner", tenant_id=str(user.tenant_id))
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "tenant_id": str(user.tenant_id), "role": user.role, "on_duty": user.on_duty}
