"""Motore licenze agnostico dal provider di pagamento.

Un solo punto che CREA ed EMETTE le license key, riusabile da qualsiasi sorgente:
- PayPal (webhook automatico) → carte + PayPal
- bonifico bancario (endpoint admin manuale)
- Stripe/Paddle in futuro (stessa funzione issue_license)

Idempotente per `external_id` (id pagamento/abbonamento): i webhook vengono
rispediti più volte, non dobbiamo emettere doppioni.
"""
import os
import ssl
import smtplib
import secrets
import string
import asyncio
import logging
from email.message import EmailMessage
from datetime import datetime, timedelta

from sqlalchemy import select

from db import AsyncSession, LicenseKey

log = logging.getLogger("papp.licensing")

APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "https://app.phai.io")
_ALPHABET = string.ascii_uppercase + string.digits  # niente lettere ambigue? teniamo semplice


def generate_key() -> str:
    """Key leggibile tipo  A1B2C-3D4E5-F6G7H-8J9K0  (4 gruppi da 5)."""
    groups = ["".join(secrets.choice(_ALPHABET) for _ in range(5)) for _ in range(4)]
    return "-".join(groups)


async def issue_license(
    email: str | None,
    plan: str = "pro",
    source: str = "manual",
    external_id: str | None = None,
    months: int | None = None,
) -> dict:
    """Crea ed emette una license key. Idempotente per external_id.
    `months`: durata abbonamento (None = senza scadenza, es. lifetime/manuale).
    Ritorna {key, reused}."""
    plan = (plan or "pro").strip().lower()
    if plan not in ("starter", "pro", "elite"):
        plan = "pro"
    async with AsyncSession() as s:
        if external_id:
            existing = (
                await s.execute(select(LicenseKey).where(LicenseKey.external_id == external_id))
            ).scalar_one_or_none()
            if existing:
                log.info("Licenza già emessa per %s (riuso %s)", external_id, existing.key)
                return {"key": existing.key, "reused": True}
        # genera una key unica
        key = generate_key()
        for _ in range(6):
            dup = (await s.execute(select(LicenseKey).where(LicenseKey.key == key))).scalar_one_or_none()
            if not dup:
                break
            key = generate_key()
        expires = datetime.utcnow() + timedelta(days=31 * months) if months else None
        lk = LicenseKey(
            key=key, plan=plan, active=True, revoked=False, expires_at=expires,
            source=source, external_id=external_id, buyer_email=(email or None),
        )
        s.add(lk)
        await s.commit()
    log.info("Licenza emessa key=%s plan=%s source=%s email=%s", key, plan, source, email)
    if email:
        await send_license_email(email, key, plan)
    return {"key": key, "reused": False}


async def set_active_by_external(external_id: str, active: bool) -> bool:
    """Attiva/disattiva la licenza legata a un abbonamento (es. PayPal cancel →
    active=False → l'EA smette di aprire). Ritorna True se trovata."""
    async with AsyncSession() as s:
        lk = (
            await s.execute(select(LicenseKey).where(LicenseKey.external_id == external_id))
        ).scalar_one_or_none()
        if not lk:
            return False
        lk.active = active
        await s.commit()
    log.info("Licenza %s -> active=%s (external_id=%s)", lk.key, active, external_id)
    return True


# --------------------------------------------------------------------------
# Email di consegna della key (SMTP opzionale: se non configurato, logga la key)
# --------------------------------------------------------------------------
def _smtp_cfg():
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASS", ""),
        "from": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@phai.io")),
        "tls": os.getenv("SMTP_TLS", "1") == "1",
    }


def _send_email_sync(cfg, to_addr: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    if cfg["tls"]:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as srv:
            srv.starttls(context=ctx)
            if cfg["user"]:
                srv.login(cfg["user"], cfg["password"])
            srv.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as srv:
            if cfg["user"]:
                srv.login(cfg["user"], cfg["password"])
            srv.send_message(msg)


async def send_license_email(email: str, key: str, plan: str):
    cfg = _smtp_cfg()
    subject = "La tua licenza PHAI Trading 🔑"
    body = (
        f"Grazie per aver scelto PHAI Trading!\n\n"
        f"La tua License Key ({plan}):\n\n    {key}\n\n"
        f"Come iniziare:\n"
        f"1) Registra il tuo account: {APP_PUBLIC_URL}\n"
        f"   (usa questa License Key durante la registrazione)\n"
        f"2) Segui la guida d'installazione che trovi nell'area clienti.\n\n"
        f"Hai bisogno di aiuto? Rispondi a questa email.\n\n"
        f"Il team PHAI\n"
        f"---\n"
        f"Il trading comporta rischi. Nessun rendimento è garantito.\n"
    )
    if not cfg:
        log.warning("SMTP non configurato: key %s per %s NON inviata via email (configura SMTP_*).", key, email)
        return
    try:
        await asyncio.get_event_loop().run_in_executor(None, _send_email_sync, cfg, email, subject, body)
        log.info("Email licenza inviata a %s", email)
    except Exception:
        log.exception("Invio email licenza fallito (key %s resta valida)", key)
