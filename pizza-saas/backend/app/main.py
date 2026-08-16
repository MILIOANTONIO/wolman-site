import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth.google_oauth import router as google_auth_router
from app.auth.router import router as auth_router
from app.config import FRONTEND_URL, SESSION_SECRET_KEY
from app.db import SessionLocal
from app.routers.admin import router as admin_router
from app.routers.agent_tools import router as agent_tools_router
from app.routers.dashboard import router as dashboard_router
from app.routers.elevenlabs_webhook import router as elevenlabs_webhook_router
from app.routers.onboarding import router as onboarding_router
from app.routers.onboarding import UPLOADS_DIR
from app.routers.promoziona_content import router as promoziona_content_router
from app.routers.public import router as public_router
from app.routers.push import router as push_router
from app.routers.team import router as team_router
from app.routers.whatsapp_webhook import router as whatsapp_router
from app.routers.ws import router as ws_router
from app.services.billing_enforcement import run_enforcement_cycle

# Ogni quante ore ricontrollare rinnovi/sospensioni/cancellazioni numeri -
# non serve piu' frequente: i periodi di grazia si contano in giorni.
ENFORCEMENT_INTERVAL_HOURS = 6


async def _enforcement_loop():
    while True:
        try:
            async with SessionLocal() as db:
                await run_enforcement_cycle(db)
        except Exception as e:
            sys.stderr.write(f"Ciclo di enforcement fatturazione fallito: {e}\n")
        await asyncio.sleep(ENFORCEMENT_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_enforcement_loop())
    yield
    task.cancel()


app = FastAPI(title="Pizza SaaS API", lifespan=lifespan)

# Necessaria solo per lo scambio di stato OAuth (Authlib) - separata dal
# cookie di sessione applicativo emesso in app/auth/session.py.
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.path.dirname(UPLOADS_DIR)), name="uploads")

app.include_router(auth_router)
app.include_router(google_auth_router)
app.include_router(onboarding_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(team_router)
app.include_router(push_router)
app.include_router(public_router)
app.include_router(agent_tools_router)
app.include_router(elevenlabs_webhook_router)
app.include_router(whatsapp_router)
app.include_router(ws_router)
app.include_router(promoziona_content_router)


@app.get("/api/health")
async def health():
    return {"ok": True}
