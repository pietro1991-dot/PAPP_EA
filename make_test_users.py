#!/usr/bin/env python3
"""Crea un utente di test per OGNI tipologia di cliente. Ri-eseguibile (idempotente)."""
import os, asyncio, pathlib

# carica DATABASE_URL (e altro) da chat_bot/.env
envf = pathlib.Path("chat_bot/.env")
if not envf.exists():
    envf = pathlib.Path(".env")
for line in envf.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import sys
sys.path.insert(0, "chat_bot")
from sqlalchemy import select, delete
import db
from db import AsyncSession, User, LicenseKey
from auth import hash_password

PASSWORD = "PhaiTest2026"

# (email, plan/SKU o None per free, etichetta, cosa può fare)
USERS = [
    ("test-free@papp.it",       None,              "Free / Demo",          "assistente base (limite giornaliero), NESSUN segnale, NESSUN EA"),
    ("test-signals@papp.it",    "signals",         "Assistente + Segnali", "segnali + PUSH + assistente illimitato, nessun EA"),
    ("test-single@papp.it",     "single:EURUSD",   "Singolo EA (EUR/USD)", "1 EA EUR/USD + segnali + assistente"),
    ("test-difensivo@papp.it",  "pack_difensivo",  "Pacchetto Difensivo",  "EUR/USD + EUR/GBP + segnali + assistente"),
    ("test-bilanciato@papp.it", "pack_bilanciato", "Pacchetto Bilanciato", "EUR/USD + EUR/GBP + GBP/CHF + segnali + assistente"),
    ("test-completo@papp.it",   "pack_completo",   "Pacchetto Completo",   "TUTTI e 5 gli EA + segnali + assistente PREMIUM"),
]


def keyfor(plan):
    slug = plan.replace(":", "-").replace("_", "-").upper()
    return f"TEST-{slug}"


async def main():
    ph = hash_password(PASSWORD)
    out = []
    async with AsyncSession() as s:
        for email, plan, label, cando in USERS:
            # pulizia (idempotenza): via l'utente e la sua licenza di test
            await s.execute(delete(User).where(User.email == email))
            if plan:
                await s.execute(delete(LicenseKey).where(LicenseKey.key == keyfor(plan)))
            await s.flush()
            lk_key = None
            if plan:
                lk = LicenseKey(key=keyfor(plan), plan=plan, active=True, revoked=False,
                                source="manual", buyer_email=email)
                s.add(lk); await s.flush()
                lk_key = lk.key
            u = User(email=email, password_hash=ph, license_key=lk_key)
            s.add(u); await s.flush()
            if lk_key:
                await s.execute(
                    LicenseKey.__table__.update().where(LicenseKey.key == lk_key).values(used_by_user_id=u.id)
                )
            out.append((email, label, plan or "(nessuno)", cando, u.id))
        await s.commit()
    print(f"Creati/aggiornati {len(out)} utenti. Password unica: {PASSWORD}\n")
    for email, label, plan, cando, uid in out:
        print(f"  [{label}] {email}  (uid {uid}, plan={plan})\n      -> {cando}")
    return out


asyncio.run(main())
