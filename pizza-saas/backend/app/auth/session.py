"""
Sessione utente firmata (cookie httpOnly), niente tabella "sessions" in DB:
il cookie stesso contiene {sub, role, tenant_id} firmato con itsdangerous,
verificato ad ogni richiesta. Ruoli: "owner" (proprietario tenant) o "admin".
"""
import uuid

from fastapi import Cookie, Depends, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import FRONTEND_URL, SESSION_SECRET_KEY
from app.db import get_db
from app.models import AdminUser, User

# Nome diverso da "session": la SessionMiddleware di Starlette (usata da
# Authlib per lo stato OAuth in app/auth/google_oauth.py) usa di default un
# cookie chiamato "session" - se il nostro avesse lo stesso nome, veniva
# sovrascritto nella stessa risposta subito dopo averlo impostato, causando
# un logout immediato e silenzioso ad ogni login.
COOKIE_NAME = "ps_session"
MAX_AGE_SECONDS = 30 * 24 * 3600  # 30 giorni

# Un cookie "Secure" viene inviato dal browser solo su HTTPS: in locale
# (http://localhost) andrebbe perso in modo intermittente, causando
# disconnessioni casuali. Lo attiviamo solo quando il frontend gira davvero
# su HTTPS (produzione).
_COOKIE_SECURE = FRONTEND_URL.startswith("https://")
# In produzione frontend e backend sono su due sottodomini onrender.com
# diversi, che il browser tratta come siti diversi ai fini di SameSite: con
# "Lax" il cookie arriva sul redirect di login (navigazione top-level) ma
# viene bloccato sulle chiamate fetch/XHR successive del frontend (es.
# GET /api/auth/me), che sembrano quindi sempre "non autenticato" anche
# subito dopo un login Google riuscito. "None" richiede Secure=True, quindi
# va bene solo quando siamo gia' su HTTPS (mai in locale su http://).
_COOKIE_SAMESITE = "none" if _COOKIE_SECURE else "lax"

_serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY, salt="pizza-saas-session")


def issue_session_cookie(response: Response, *, sub: str, role: str, tenant_id: str | None = None):
    token = _serializer.dumps({"sub": sub, "role": role, "tenant_id": tenant_id})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


def _read_session(session: str | None):
    if not session:
        return None
    try:
        return _serializer.loads(session, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


async def get_current_user(
    ps_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = _read_session(ps_session)
    if not payload or payload.get("role") != "owner":
        raise HTTPException(status_code=401, detail="Non autenticato")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="Non autenticato")
    return user


async def get_current_admin(
    ps_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    payload = _read_session(ps_session)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Non autenticato")
    admin = await db.get(AdminUser, uuid.UUID(payload["sub"]))
    if not admin:
        raise HTTPException(status_code=401, detail="Non autenticato")
    return admin


def require_roles(*allowed_roles: str):
    """
    Dependency factory per limitare un endpoint ai soli sotto-account con un
    certo User.role (owner/cuoco/receptionista/delivery) - diverso dal
    "role" del cookie di sessione (che distingue solo portale proprietario
    da portale admin, sempre "owner" per qualunque utente del tenant).
    """
    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Non hai i permessi per questa sezione")
        return user

    return _dependency


get_current_owner = require_roles("owner")


async def get_optional_user(
    ps_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    payload = _read_session(ps_session)
    if not payload or payload.get("role") != "owner":
        return None
    return await db.get(User, uuid.UUID(payload["sub"]))
