"""
Login "Accedi con Google" per proprietari tenant e admin, via Authlib.
Il ruolo (owner/admin) viaggia nello state OAuth per sapere, al callback,
cosa fare col profilo Google restituito.
"""
import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth.session import issue_session_cookie
from app.config import FRONTEND_URL, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
from app.db import SessionLocal
from app.models import AdminUser, Tenant, TenantSettings, User

router = APIRouter(prefix="/api/auth/google", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_OAUTH_CLIENT_ID,
    client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request, role: str = "owner"):
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=400, detail="role non valido")
    request.session["oauth_role"] = role
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="google_callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    google_sub = userinfo.get("sub")
    role = request.session.pop("oauth_role", "owner")

    if not email or not google_sub:
        raise HTTPException(status_code=400, detail="Profilo Google incompleto")

    async with SessionLocal() as db:
        if role == "admin":
            admin = await _find_or_reject_admin(db, email, google_sub)
            response = RedirectResponse(url=f"{FRONTEND_URL}/admin")
            issue_session_cookie(response, sub=str(admin.id), role="admin")
            return response

        user = await _find_or_create_owner(db, email, google_sub)
        response = RedirectResponse(url=f"{FRONTEND_URL}/onboarding")
        issue_session_cookie(response, sub=str(user.id), role="owner", tenant_id=str(user.tenant_id))
        return response


async def _find_or_reject_admin(db, email, google_sub) -> AdminUser:
    result = await db.execute(select(AdminUser).where(AdminUser.google_sub == google_sub))
    admin = result.scalar_one_or_none()
    if admin:
        return admin
    result = await db.execute(select(AdminUser).where(AdminUser.email == email))
    admin = result.scalar_one_or_none()
    if not admin:
        # Gli admin non si auto-registrano: vanno creati a mano in DB per sicurezza.
        raise HTTPException(status_code=403, detail="Questo account non ha accesso al pannello admin")
    admin.google_sub = google_sub
    await db.commit()
    await db.refresh(admin)
    return admin


async def _find_or_create_owner(db, email, google_sub) -> User:
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()
    if user:
        return user

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.google_sub = google_sub
        await db.commit()
        await db.refresh(user)
        return user

    # Primo accesso: crea un tenant vuoto, l'onboarding lo completa dopo.
    tenant = Tenant(business_name="", slug=f"nuovo-{uuid.uuid4().hex[:8]}", status="pending_kyc")
    db.add(tenant)
    await db.flush()

    db.add(TenantSettings(tenant_id=tenant.id))

    user = User(tenant_id=tenant.id, email=email, google_sub=google_sub, role="owner")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
