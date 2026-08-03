import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth.google_oauth import router as google_auth_router
from app.auth.router import router as auth_router
from app.config import FRONTEND_URL, SESSION_SECRET_KEY
from app.routers.admin import router as admin_router
from app.routers.agent_tools import router as agent_tools_router
from app.routers.dashboard import router as dashboard_router
from app.routers.elevenlabs_webhook import router as elevenlabs_webhook_router
from app.routers.onboarding import router as onboarding_router
from app.routers.onboarding import UPLOADS_DIR
from app.routers.whatsapp_webhook import router as whatsapp_router
from app.routers.ws import router as ws_router

app = FastAPI(title="Pizza SaaS API")

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
app.include_router(agent_tools_router)
app.include_router(elevenlabs_webhook_router)
app.include_router(whatsapp_router)
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"ok": True}
