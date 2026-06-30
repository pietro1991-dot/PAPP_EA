"""Motore drip della campagna email — pilotato dal nostro stack, consegna via Brevo.

Tutto è DERIVATO dallo stato del DB (nessun hook nel resto dell'app):
- NURTURE: parte da leads.created_at; si ferma se il lead diventa cliente.
- CODA (postseq): solo a chi NON ha acquistato.
- ONBOARDING: per ogni cliente (User+licenza valida). 'primo dato' = primo Signal/Account
  del cliente; 'nessun dato 24h' = nessun dato dopo 24h dall'acquisto.
- RETENTION: settimanale, recap mensile, mese-piatto (0 trade in 30g), upsell
  (Starter→Pro, Pro→Annuale, Elite per heavy-user AI), referral, win-back (licenza scaduta).

Consegna: Brevo API (BREVO_API_KEY) → fallback SMTP (SMTP_*) → dry-run (logga).
Anti-raffica: le email a tempo arretrate oltre DRIP_SKIP_OLDER_HOURS (36h) vengono saltate.
Le ricorrenti (settimanale/mensile/flat) usano un dedup per-periodo, quindi ripartono ogni periodo.

  python3 email_drip.py tick [--dry]
  python3 email_drip.py status
"""
import os
import re
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select, func, text

from db import AsyncSession, Lead, User, LicenseKey, Signal, AccountSnapshot, ChatHistory, EmailSent
import entitlements
import catalog

log = logging.getLogger("papp.drip")

BASE = os.path.dirname(os.path.abspath(__file__))


def _load_lang(lang):
    """Carica i contenuti email per una lingua: email_campaign.json (it) o
    email_campaign.<lang>.json. Ritorna {id: email} o None se il file non c'è."""
    fn = "email_campaign.json" if lang == "it" else f"email_campaign.{lang}.json"
    p = os.path.join(BASE, fn)
    if os.path.exists(p):
        return {e["id"]: e for e in json.load(open(p, encoding="utf-8"))}
    return None


CAMPAIGN = json.load(open(os.path.join(BASE, "email_campaign.json"), encoding="utf-8"))  # struttura/sequenze (IT)
CAMP_LANG = {lg: d for lg in ("it", "en", "fr", "es") if (d := _load_lang(lg))}


def content(lang, eid):
    """Email nella lingua del contatto; fallback all'italiano se manca la traduzione."""
    d = CAMP_LANG.get(lang) or CAMP_LANG["it"]
    return d.get(eid) or CAMP_LANG["it"][eid]
APP = os.getenv("APP_PUBLIC_URL", "https://app.phai.io").rstrip("/")
SKIP_OLDER_HOURS = int(os.getenv("DRIP_SKIP_OLDER_HOURS", "36"))
VALID_PLANS = ("starter", "pro", "elite")

LINKS = {
    "{{demo}}": f"{APP}/demo", "{{sblocca}}": f"{APP}/checkout?plan=pro",
    "{{report}}": f"{APP}/report", "{{guida}}": f"{APP}/report",
    "{{dfy}}": f"{APP}/checkout?plan=pro", "{{app}}": APP, "{{referral}}": f"{APP}/referral",
}


_NAME_PH = r"\[(?:Nome|Name|Nom|Nombre|nome)\]"


def _personalize(text, email, name="", license_key=""):
    for k, v in LINKS.items():
        text = text.replace(k, v)
    text = text.replace("{{unsubscribe}}", f"{APP}/unsub?e={email}")
    text = text.replace("{{license_key}}", license_key or "")
    # Nome del contatto: se non lo conosciamo (abbiamo solo l'email), togliamo il
    # segnaposto lasciando un saluto naturale ("Ciao [Nome]," → "Ciao,"; "[Nome], x" → "x").
    if name:
        text = re.sub(_NAME_PH, name, text)
    else:
        text = re.sub(r"\s*" + _NAME_PH, "", text)
        text = re.sub(r"(?m)^[ \t]*,[ \t]*", "", text)
    return re.sub(r"\{\{[^}]+\}\}", "", text)


def _smtp_send(host, msg):
    import smtplib, ssl
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        if os.getenv("SMTP_TLS", "1") == "1":
            s.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
        s.send_message(msg)


async def _send(to, subject, text):
    sender = os.getenv("SMTP_FROM", "PHAI Trading <no-reply@phai.io>")
    m = re.search(r"<([^>]+)>", sender)
    sender_email = m.group(1) if m else sender
    key = os.getenv("BREVO_API_KEY")
    if key:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post("https://api.brevo.com/v3/smtp/email",
                                 headers={"api-key": key, "accept": "application/json", "content-type": "application/json"},
                                 json={"sender": {"name": "PHAI Trading", "email": sender_email},
                                       "to": [{"email": to}], "subject": subject, "textContent": text})
            return "sent" if r.status_code < 300 else "error"
        except Exception:
            log.exception("Brevo invio fallito"); return "error"
    if os.getenv("SMTP_HOST"):
        from email.message import EmailMessage
        try:
            msg = EmailMessage(); msg["From"] = sender; msg["To"] = to; msg["Subject"] = subject; msg.set_content(text)
            await asyncio.get_event_loop().run_in_executor(None, _smtp_send, os.getenv("SMTP_HOST"), msg)
            return "sent"
        except Exception:
            log.exception("SMTP invio fallito"); return "error"
    return "dry"


async def _record(email, store_id, status):
    async with AsyncSession() as s:
        s.add(EmailSent(email=email, email_id=store_id, status=status))
        try:
            await s.commit()
        except Exception:
            await s.rollback()


async def tick(dry=False):
    stats = {"sent": 0, "skipped": 0}

    async with AsyncSession() as s:
        # Orologio dal DB in ora LOCALE naive (come i created_at, che func.now() salva
        # nel fuso della sessione) → confronti coerenti, niente sfasamento UTC.
        now = (await s.execute(text("SELECT localtimestamp"))).scalar()
        week = now.strftime("%G-W%V")
        month = now.strftime("%Y-%m")
        leads = (await s.execute(select(Lead))).scalars().all()
        unsub = {l.email for l in leads if l.unsubscribed}   # disiscrizione globale (lead o cliente)
        lang_map = {l.email: (l.lang or "it") for l in leads}  # lingua per contatto
        customer_emails = set((await s.execute(select(User.email))).scalars().all())
        done = {(r.email, r.email_id) for r in (await s.execute(select(EmailSent))).scalars().all()}
        cust_rows = (await s.execute(
            select(User.id, User.email, User.created_at, User.license_key,
                   LicenseKey.plan, LicenseKey.active, LicenseKey.revoked, LicenseKey.expires_at)
            .join(LicenseKey, LicenseKey.key == User.license_key)
        )).all()

        cur_lang = "it"   # lingua del contatto corrente (impostata nei loop)

        async def emit(email, base_id, store_id, due_at, name="", lk="", skip_guard=True):
            """Invia (o logga) un'email se dovuta e non già inviata. Ritorna True se inviata."""
            if email in unsub or (email, store_id) in done:
                return False
            if due_at is None or due_at > now:
                return False
            if skip_guard and (now - due_at) > timedelta(hours=SKIP_OLDER_HOURS):
                done.add((email, store_id))
                if not dry:
                    await _record(email, store_id, "skipped")
                stats["skipped"] += 1
                return False
            e = content(cur_lang, base_id)
            body = _personalize(e["body"], email, name, lk)
            if dry:
                print(f"  [DRY] → {email:30} {store_id:26} | {e['subject']}")
            else:
                st = await _send(email, e["subject"], body)
                await _record(email, store_id, "sent" if st in ("sent", "dry") else "error")
            done.add((email, store_id))
            stats["sent"] += 1
            return True

        # ---------- NURTURE + CODA (dai lead) ----------
        nurture = [e for e in CAMPAIGN if e["sequence"] == "nurture"]
        postseq = [e for e in CAMPAIGN if e["sequence"] == "postseq"]
        for lead in leads:
            if lead.unsubscribed:
                continue
            cur_lang = lead.lang or "it"
            base = lead.created_at or now
            converted = lead.email in customer_emails
            for e in nurture:
                if converted:
                    continue  # diventato cliente → passa all'onboarding
                await emit(lead.email, e["id"], e["id"], base + timedelta(days=e["delay_days"]), skip_guard=True)
            for e in postseq:
                if converted:
                    continue
                await emit(lead.email, e["id"], e["id"], base + timedelta(days=e["delay_days"]), skip_guard=True)

        # ---------- ONBOARDING + RETENTION (dai clienti) ----------
        for uid, email, ucreated, lkey, plan, active, revoked, expires in cust_rows:
            cur_lang = lang_map.get(email, "it")   # lingua del cliente (dal lead) o IT
            plan = (plan or "").lower()
            # "valid" = qualsiasi SKU pagante (signals / singolo EA / pacchetto / portfolio / legacy)
            valid = entitlements.can_signals(plan) and active is not False and not revoked and \
                    (expires is None or expires >= now)
            purchase = ucreated or now

            # WIN-BACK: licenza scaduta di recente → una volta
            if not valid and expires is not None and expires < now:
                await emit(email, "retention-winback", "retention-winback", expires, lk=lkey, skip_guard=False)
                continue
            if not valid:
                continue

            # primo dato EA del cliente (min created_at tra signals e account snapshots)
            d1 = (await s.execute(select(func.min(Signal.created_at)).where(Signal.user_id == uid))).scalar()
            d2 = (await s.execute(select(func.min(AccountSnapshot.created_at)).where(AccountSnapshot.user_id == uid))).scalar()
            firsts = [x for x in (d1, d2) if x]
            first_data = min(firsts) if firsts else None
            has_data = first_data is not None

            # ONBOARDING
            await emit(email, "onboarding-1", "onboarding-1", purchase, lk=lkey)          # benvenuto + key
            if not has_data:
                await emit(email, "onboarding-2", "onboarding-2", purchase + timedelta(days=1))  # install help
            else:
                await emit(email, "onboarding-3", "onboarding-3", first_data)              # Sei LIVE
                await emit(email, "onboarding-4", "onboarding-4", first_data + timedelta(days=3))
                await emit(email, "onboarding-5", "onboarding-5", first_data + timedelta(days=7))
                await emit(email, "onboarding-6", "onboarding-6", first_data + timedelta(days=14))

            # RETENTION ricorrenti (dedup per periodo) — solo clienti operativi
            if has_data:
                await emit(email, "retention-weekly", f"retention-weekly:{week}", now, skip_guard=False)
                await emit(email, "retention-monthly", f"retention-monthly:{month}", now, skip_guard=False)
                trades30 = (await s.execute(
                    select(func.count(Signal.id)).where(
                        Signal.user_id == uid, Signal.action.in_(("open", "close")),
                        Signal.created_at >= now - timedelta(days=30)))).scalar() or 0
                if trades30 == 0:
                    await emit(email, "retention-flat", f"retention-flat:{month}", now, skip_guard=False)

            # UPSELL / REFERRAL (una volta, quando idoneo) — basato su EA posseduti e tier
            owned = entitlements.owned_eas(plan)
            total = len(catalog.ALL_EA_IDS)
            if owned and len(owned) < total:        # possiede qualche EA ma non tutti → sblocca altre strategie
                await emit(email, "retention-upsell-pro", "retention-upsell-pro", purchase + timedelta(days=7), skip_guard=False)
            await emit(email, "retention-upsell-annual", "retention-upsell-annual", purchase + timedelta(days=90), skip_guard=False)
            chat_n = (await s.execute(select(func.count(ChatHistory.id)).where(ChatHistory.user_id == uid))).scalar() or 0
            if entitlements.chatbot_tier(plan) != "premium" and chat_n >= 15:   # forte uso AI ma non ancora Portfolio
                await emit(email, "retention-elite", "retention-elite", now, skip_guard=False)
            await emit(email, "retention-referral", "retention-referral", purchase + timedelta(days=30), skip_guard=False)

    print(f"{'[DRY] ' if dry else ''}inviate: {stats['sent']} · saltate: {stats['skipped']}")


async def status():
    async with AsyncSession() as s:
        nleads = (await s.execute(select(func.count(Lead.id)))).scalar()
        nunsub = (await s.execute(select(func.count(Lead.id)).where(Lead.unsubscribed.is_(True)))).scalar()
        nsent = (await s.execute(select(func.count(EmailSent.id)).where(EmailSent.status == "sent"))).scalar()
        ncust = (await s.execute(select(func.count(User.id)).join(LicenseKey, LicenseKey.key == User.license_key)
                                 .where(LicenseKey.plan.isnot(None), LicenseKey.plan != ""))).scalar()
    provider = "Brevo" if os.getenv("BREVO_API_KEY") else ("SMTP" if os.getenv("SMTP_HOST") else "DRY")
    print(f"Lead: {nleads} (disiscritti {nunsub}) · clienti: {ncust} · email inviate: {nsent} · provider: {provider}")
    print(f"Campagna: {len(CAMPAIGN)} email (nurture/onboarding/retention/coda)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    asyncio.run(tick(dry="--dry" in sys.argv) if cmd == "tick" else status())
