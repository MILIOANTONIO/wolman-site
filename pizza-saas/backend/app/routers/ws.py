"""
WebSocket per la dashboard ordini in tempo reale. Mappa di connessioni in
memoria (un solo processo web per l'MVP) - se in futuro serve più di
un'istanza, questo va sostituito con Redis pub/sub (già segnalato come
lavoro di fase 2 nel piano).
"""
import json
import uuid
from collections import defaultdict

from fastapi import APIRouter, Cookie, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import COOKIE_NAME, _read_session
from app.db import SessionLocal
from app.models import User

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, tenant_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[tenant_id].append(ws)

    def disconnect(self, tenant_id: str, ws: WebSocket):
        if ws in self._connections[tenant_id]:
            self._connections[tenant_id].remove(ws)

    async def broadcast(self, tenant_id: str, message: dict):
        dead = []
        for ws in self._connections.get(tenant_id, []):
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)


manager = ConnectionManager()


@router.websocket("/ws/tenant/{tenant_id}/orders")
async def orders_ws(websocket: WebSocket, tenant_id: str, ps_session: str | None = Cookie(default=None, alias=COOKIE_NAME)):
    payload = _read_session(ps_session)
    if not payload or payload.get("role") != "owner" or payload.get("tenant_id") != tenant_id:
        await websocket.close(code=4401)
        return

    await manager.connect(tenant_id, websocket)
    try:
        while True:
            # Il client non deve mandare nulla: teniamo la connessione viva
            # e ignoriamo eventuali messaggi in arrivo.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(tenant_id, websocket)
