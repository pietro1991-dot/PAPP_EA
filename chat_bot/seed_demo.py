"""Crea/aggiorna l'utente demo (demo@phai.io) con dati di esempio per la Demo
read-only pubblica (route /demo). Idempotente: rifare il seed pulisce e ricrea.

Uso:  python3 seed_demo.py
L'email è configurabile via env DEMO_EMAIL (default demo@phai.io).
"""
import os
import asyncio
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, delete

from db import AsyncSession, User, Signal, AccountSnapshot, init_db
import auth

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@phai.io")


async def main():
    await init_db()
    async with AsyncSession() as s:
        u = (await s.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
        if not u:
            u = User(email=DEMO_EMAIL, password_hash=auth.hash_password(secrets.token_urlsafe(16)))
            s.add(u)
            await s.flush()
        uid = u.id
        await s.execute(delete(Signal).where(Signal.user_id == uid))
        await s.execute(delete(AccountSnapshot).where(AccountSnapshot.user_id == uid))
        now = datetime.utcnow()
        sig = [
            dict(symbol="EURUSD", action="open", pattern=1, dir="SELL", entry=1.08500, sl=1.1020, tp=1.0700, lot=0.30, reason="SETUP|e:30|d:2|sl:365|tp:150", t=now - timedelta(hours=2)),
            dict(symbol="EURUSD", action="close", pattern=4, dir="SELL", pnl_pt=123, reason="R|tp", t=now - timedelta(hours=20)),
            dict(symbol="GBPUSD", action="open", pattern=1, dir="SELL", entry=1.27100, reason="SETUP|e:182|d:2|x:3|sl:121", t=now - timedelta(hours=26)),
            dict(symbol="EURUSD", action="close", pattern=6, dir="BUY", pnl_pt=95, reason="R|tp", t=now - timedelta(days=2)),
            dict(symbol="USDCHF", action="skip", pattern=7, dir="SELL", reason="R|skip_spread", t=now - timedelta(days=2, hours=3)),
            dict(symbol="USDCHF", action="close", pattern=1, dir="SELL", pnl_pt=-32, reason="R|sl", t=now - timedelta(days=3)),
            dict(symbol="GBPUSD", action="open", pattern=3, dir="BUY", entry=1.26050, reason="SETUP|e:121|d:1|x:30", t=now - timedelta(days=4)),
        ]
        for d in sig:
            s.add(Signal(user_id=uid, **d))
        s.add(AccountSnapshot(user_id=uid, symbol="EURUSD", balance=10000, equity=10180, margin=420,
                              free_margin=9760, margin_level=2424, profit=180, sym_profit=80, sym_pct=0.8, sym_open=1, t=now))
        await s.commit()
        print(f"Demo seedata: user_id={uid} ({DEMO_EMAIL}), {len(sig)} segnali + 1 snapshot conto")


if __name__ == "__main__":
    asyncio.run(main())
