"""Migrazione NON distruttiva: crea le tabelle nuove (users, license_keys,
llm_cache) e aggiunge la colonna chat_history.user_id se manca. Idempotente.
Uso: python3 migrate.py   (preserva i dati esistenti di signals/chat)."""
import asyncio

from sqlalchemy import text

from db import engine, init_db


async def main():
    await init_db()  # create_all: crea solo le tabelle mancanti
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS user_id INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE signals ADD COLUMN IF NOT EXISTS symbol VARCHAR(20)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_signals_symbol ON signals (symbol)")
        )
    print("Migrazione completata (dati preservati).")


if __name__ == "__main__":
    asyncio.run(main())
