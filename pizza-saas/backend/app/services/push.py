"""
Invio notifiche push (Web Push standard, funziona su Chrome/Edge/Firefox e
Safari da iOS 16.4 - su iPhone richiede però che l'app sia stata prima
installata come da schermata Home, non basta visitare il sito).
"""
import asyncio
import json
import sys

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import VAPID_CONTACT_EMAIL, VAPID_PRIVATE_KEY_RAW
from app.models import PushSubscription, User


def _send_one(subscription: PushSubscription, title: str, body: str, url: str) -> bool:
    """Ritorna False se l'iscrizione non è più valida (va rimossa)."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY_RAW,
            vapid_claims={"sub": f"mailto:{VAPID_CONTACT_EMAIL}"},
        )
        return True
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return False  # iscrizione scaduta/revocata, va ripulita
        sys.stderr.write(f"Push fallito ({status}): {e}\n")
        return True  # errore transitorio, non cancellare l'iscrizione
    except Exception as e:
        # Qualunque altro errore (es. chiavi salvate corrotte/malformate):
        # non deve propagarsi ed interrompere l'invio alle altre iscrizioni
        # nello stesso asyncio.gather - la consideriamo da ripulire.
        sys.stderr.write(f"Push fallito per iscrizione {subscription.id}: {e}\n")
        return False


async def send_push_to_users(db: AsyncSession, *, user_ids: list, title: str, body: str, url: str = "/dashboard"):
    if not VAPID_PRIVATE_KEY_RAW or not user_ids:
        return
    rows = (await db.execute(select(PushSubscription).where(PushSubscription.user_id.in_(user_ids)))).scalars().all()
    # webpush() e' bloccante (I/O sincrono): girarla in un thread separato
    # evita di congelare l'event loop asyncio mentre contatta il servizio
    # push (Chrome/Mozilla/Apple), soprattutto con più iscrizioni da avvisare.
    results = await asyncio.gather(*[asyncio.to_thread(_send_one, sub, title, body, url) for sub in rows])
    stale_ids = [sub.id for sub, ok in zip(rows, results) if not ok]
    if stale_ids:
        for sub in rows:
            if sub.id in stale_ids:
                await db.delete(sub)
        await db.commit()


async def send_push_to_roles(db: AsyncSession, *, tenant_id, roles: list[str], title: str, body: str, url: str = "/dashboard"):
    users = (await db.execute(select(User.id).where(User.tenant_id == tenant_id, User.role.in_(roles)))).scalars().all()
    await send_push_to_users(db, user_ids=list(users), title=title, body=body, url=url)
