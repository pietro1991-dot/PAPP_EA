"""Motore drip della campagna email — pilotato dal nostro stack, consegna via Brevo.

Come funziona (zero modifiche al funnel esistente):
- la NURTURE parte dal momento in cui un Lead lascia l'email (leads.created_at);
- la CODA (postseq) va solo a chi NON ha ancora acquistato;
- ogni email è inviata UNA volta (tabella email_sent), rispettando i ritardi del piano.
- consegna: Brevo API se BREVO_API_KEY è impostata; altrimenti SMTP (SMTP_*); altrimenti
  dry-run (logga soltanto). Così è pronto: appena metti la chiave Brevo, parte.

Onboarding/retention dipendono da EVENTI dell'app (acquisto, primo dato, mese piatto):
si agganciano in un secondo momento. Qui automatizziamo l'acquisizione (nurture+coda),
la parte che conta di più al lancio.

Esecuzione periodica (es. ogni ora) via cron/systemd:
  python3 email_drip.py tick           # invia le email dovute
  python3 email_drip.py tick --dry     # mostra cosa invierebbe, senza inviare
  python3 email_drip.py status         # statistiche
"""
import os
import re
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select, func

from db import AsyncSession, Lead, User, EmailSent

log = logging.getLogger("papp.drip")

BASE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = json.load(open(os.path.join(BASE, "email_campaign.json"), encoding="utf-8"))
APP = os.getenv("APP_PUBLIC_URL", "https://app.phai.io").rstrip("/")
# Non inviare email "in ritardo" oltre questa soglia (evita raffiche al primo avvio).
SKIP_OLDER_HOURS = int(os.getenv("DRIP_SKIP_OLDER_HOURS", "36"))

# Sostituzione placeholder → URL/valori reali.
LINKS = {
    "{{demo}}": f"{APP}/demo",
    "{{sblocca}}": f"{APP}/checkout?plan=pro",
    "{{report}}": f"{APP}/report",
    "{{guida}}": f"{APP}/report",          # placeholder finché non c'è la pagina guida pubblica
    "{{dfy}}": f"{APP}/checkout?plan=pro",
    "{{app}}": APP,
    "{{referral}}": f"{APP}/referral",
}


def _personalize(text: str, email: str, name: str = "") -> str:
    for k, v in LINKS.items():
        text = text.replace(k, v)
    text = text.replace("{{unsubscribe}}", f"{APP}/unsub?e={email}")
    text = text.replace("[Nome]", name or "ciao")
    # eventuali placeholder rimasti (es. {{license_key}} non usato in nurture) → puliti
    text = re.sub(r"\{\{[^}]+\}\}", "", text)
    return text


async def _send(to: str, subject: str, text: str) -> str:
    """Consegna l'email. Ritorna 'sent' | 'dry' | 'error'."""
    sender = os.getenv("SMTP_FROM", "PHAI Trading <no-reply@phai.io>")
    sender_email = re.search(r"<([^>]+)>", sender)
    sender_email = sender_email.group(1) if sender_email else sender
    key = os.getenv("BREVO_API_KEY")
    if key:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": key, "accept": "application/json", "content-type": "application/json"},
                    json={"sender": {"name": "PHAI Trading", "email": sender_email},
                          "to": [{"email": to}], "subject": subject, "textContent": text},
                )
            return "sent" if r.status_code < 300 else "error"
        except Exception:
            log.exception("Brevo invio fallito"); return "error"
    # fallback SMTP
    host = os.getenv("SMTP_HOST")
    if host:
        import smtplib, ssl
        from email.message import EmailMessage
        try:
            msg = EmailMessage(); msg["From"] = sender; msg["To"] = to; msg["Subject"] = subject
            msg.set_content(text)
            await asyncio.get_event_loop().run_in_executor(None, _smtp_send, host, msg)
            return "sent"
        except Exception:
            log.exception("SMTP invio fallito"); return "error"
    return "dry"   # nessun provider configurato


def _smtp_send(host, msg):
    import smtplib, ssl
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        if os.getenv("SMTP_TLS", "1") == "1":
            s.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
        s.send_message(msg)


def _seq(name):
    return [e for e in CAMPAIGN if e["sequence"] == name]


async def tick(dry: bool = False):
    now = datetime.utcnow()
    nurture, postseq = _seq("nurture"), _seq("postseq")
    sent_n = skipped = 0
    async with AsyncSession() as s:
        leads = (await s.execute(select(Lead))).scalars().all()
        customers = set((await s.execute(select(User.email))).scalars().all())
        done = {(r.email, r.email_id) for r in (await s.execute(select(EmailSent))).scalars().all()}

    for lead in leads:
        if lead.unsubscribed:
            continue
        created = lead.created_at or now
        converted = lead.email in customers
        plan = nurture + postseq
        for e in plan:
            if (lead.email, e["id"]) in done:
                continue
            due = created + timedelta(days=e["delay_days"])
            if due > now:
                continue
            # la coda (postseq) va solo a chi NON ha comprato; la nurture si ferma se ha comprato
            if converted:
                # registra come 'skipped' per non riprovare
                if not dry:
                    await _record(lead.email, e["id"], "skipped")
                continue
            # troppo in ritardo (primo avvio) → salta senza inviare
            if now - due > timedelta(hours=SKIP_OLDER_HOURS):
                if not dry:
                    await _record(lead.email, e["id"], "skipped")
                skipped += 1
                continue
            subject = e["subject"]
            body = _personalize(e["body"], lead.email, name="")
            if dry:
                print(f"  [DRY] → {lead.email:32} {e['id']:12} | {subject}")
                sent_n += 1
                continue
            status = await _send(lead.email, subject, body)
            await _record(lead.email, e["id"], "sent" if status in ("sent", "dry") else "error")
            if status in ("sent", "dry"):
                sent_n += 1
                log.info("drip %s → %s (%s)", e["id"], lead.email, status)
    print(f"{'[DRY] ' if dry else ''}inviate: {sent_n} · saltate(vecchie/convertite): {skipped}")


async def _record(email, email_id, status):
    async with AsyncSession() as s:
        s.add(EmailSent(email=email, email_id=email_id, status=status))
        try:
            await s.commit()
        except Exception:
            await s.rollback()


async def status():
    async with AsyncSession() as s:
        nleads = (await s.execute(select(func.count(Lead.id)))).scalar()
        nunsub = (await s.execute(select(func.count(Lead.id)).where(Lead.unsubscribed.is_(True)))).scalar()
        nsent = (await s.execute(select(func.count(EmailSent.id)).where(EmailSent.status == "sent"))).scalar()
    provider = "Brevo" if os.getenv("BREVO_API_KEY") else ("SMTP" if os.getenv("SMTP_HOST") else "DRY (nessun provider)")
    print(f"Lead: {nleads} (disiscritti {nunsub}) · email inviate: {nsent} · provider: {provider}")
    print(f"Campagna: {len(CAMPAIGN)} email · nurture {len(_seq('nurture'))} · coda {len(_seq('postseq'))}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    from db import DATABASE_URL  # noqa: assicura il caricamento env via chiamante
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    dry = "--dry" in sys.argv
    if cmd == "tick":
        asyncio.run(tick(dry=dry))
    else:
        asyncio.run(status())
