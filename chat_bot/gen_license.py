"""Genera N license key e le inserisce in tabella. Uso: python3 gen_license.py [N]
Le chiavi stampate vanno consegnate ai compratori dell'EA (una per acquirente)."""
import asyncio
import secrets
import sys

from db import AsyncSession, LicenseKey, init_db


def _make_key() -> str:
    raw = secrets.token_hex(10).upper()  # 20 hex chars
    return "-".join(raw[i:i + 5] for i in range(0, 20, 5))  # PAPP-XXXXX-XXXXX-...


async def main(n: int):
    await init_db()
    keys = [_make_key() for _ in range(n)]
    async with AsyncSession() as session:
        for k in keys:
            session.add(LicenseKey(key=k))
        await session.commit()
    print(f"Generate {n} license key:")
    for k in keys:
        print(" ", k)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(n))
