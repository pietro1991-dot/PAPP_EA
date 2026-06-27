"""Sistema di notifiche estensibile (Web Push).

`dispatch(title, body, ...)` invia una notifica a tutti i dispositivi iscritti.
È il punto unico da cui passano TUTTE le notifiche: per aggiungerne di nuove in
futuro (es. avvisi di rischio, riepiloghi giornalieri) basta chiamare dispatch()
con un `tag`/`url` diversi — nessun'altra modifica all'infrastruttura.
"""
import os
import json
import asyncio
import logging

from pywebpush import webpush, WebPushException
from sqlalchemy import select, delete

from db import AsyncSession, PushSubscription

log = logging.getLogger("papp.notify")

VAPID_PRIVATE_KEY_FILE = os.getenv("VAPID_PRIVATE_KEY_FILE", "vapid_private.pem")
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")


def _send(sub: PushSubscription, payload: str):
    webpush(
        subscription_info={
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        },
        data=payload,
        vapid_private_key=VAPID_PRIVATE_KEY_FILE,
        vapid_claims={"sub": VAPID_CLAIMS_EMAIL},  # dict fresco per ogni invio
    )


async def dispatch(title: str, body: str, *, tag: str = "papp", url: str = "/", data: dict | None = None,
                   user_ids: "set[int] | None" = None):
    """Invia una notifica push agli iscritti. Se `user_ids` è valorizzato, invia SOLO
    a quegli utenti (per i SEGNALI: solo abbonati con diritto). None = tutti.
    Non solleva mai; rimuove le iscrizioni scadute (404/410)."""
    payload = json.dumps({"title": title, "body": body, "tag": tag, "url": url, "data": data or {}})
    async with AsyncSession() as session:
        q = select(PushSubscription)
        if user_ids is not None:
            if not user_ids:
                return
            q = q.where(PushSubscription.user_id.in_(user_ids))
        subs = (await session.execute(q)).scalars().all()
    if not subs:
        return

    dead: list[int] = []
    for s in subs:
        try:
            await asyncio.to_thread(_send, s, payload)  # webpush è sincrono
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):
                dead.append(s.id)  # iscrizione scaduta
            else:
                log.warning("Push fallita (%s): %s", code, e)
        except Exception:
            log.exception("Errore invio push")

    if dead:
        async with AsyncSession() as session:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.id.in_(dead))
            )
            await session.commit()
        log.info("Rimosse %d iscrizioni push scadute", len(dead))
