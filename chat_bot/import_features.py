"""Importa le feature di mercato dall'export dell'indicatore (PAPP_Export*.csv)
nella tabella market_features. Una riga per barra D1.

Uso:
    python3 import_features.py [file_o_cartella ...]
    # default: cerca PAPP_Export*.csv in ../Motore base _linea-prezzo/

Il simbolo è dedotto dal nome file (PAPP_Export.csv = EURUSD, PAPP_Export_GBPUSD.csv,
PAPP_Export_USDCHF.csv...). Idempotente: re-importare sostituisce i dati del simbolo.
"""
import asyncio
import csv
import os
import re
import sys
from datetime import datetime

from sqlalchemy import select, delete, func

from db import AsyncSession, MarketFeature, init_db

DEFAULT_DIR = os.getenv(
    "FEATURES_DIR", os.path.join(os.path.dirname(__file__), "..", "Motore base _linea-prezzo")
)

# header CSV -> colonna DB
COLMAP = {
    "close": "close",
    "dMed%": "d_med",
    "d30%": "d_ma30",
    "d365%": "d_ma365",
    "cluPct": "cluster",
    "velPct": "velocity",
    "accPct": "accel",
    "volPct": "volatility",
    "orderScore": "order_score",
    "spread": "spread",
}


def symbol_from_name(fname: str) -> str:
    base = os.path.basename(fname).rsplit(".", 1)[0]
    m = re.search(r"PAPP_Export[_-]?([A-Za-z]{6})", base)
    return m.group(1).upper() if m else "EURUSD"


def _dt(s: str):
    s = (s or "").strip()
    for fmt in ("%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


def read_features(path: str, symbol: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            r = {(k or "").strip(): v for k, v in r.items()}
            t = _dt(r.get("datetime") or r.get("time") or r.get("date"))
            if not t:
                continue
            rec = {"symbol": symbol, "t": t}
            for src, dst in COLMAP.items():
                rec[dst] = _f(r.get(src))
            rows.append(rec)
    return rows


async def import_file(path: str):
    symbol = symbol_from_name(path)
    rows = read_features(path, symbol)
    if not rows:
        print(f"  {os.path.basename(path)}: vuoto/illeggibile, saltato")
        return 0
    async with AsyncSession() as session:
        await session.execute(delete(MarketFeature).where(MarketFeature.symbol == symbol))
        # inserimento a blocchi
        batch = []
        for r in rows:
            batch.append(MarketFeature(**r))
            if len(batch) >= 1000:
                session.add_all(batch)
                await session.flush()
                batch = []
        if batch:
            session.add_all(batch)
        await session.commit()
    print(f"  {os.path.basename(path)} → {symbol}: {len(rows)} barre importate")
    return len(rows)


async def main(args):
    await init_db()
    paths = []
    targets = args or [DEFAULT_DIR]
    for a in targets:
        if os.path.isdir(a):
            for root, _, files in os.walk(a):
                for fn in files:
                    if fn.startswith("PAPP_Export") and fn.endswith(".csv"):
                        paths.append(os.path.join(root, fn))
        elif a.endswith(".csv"):
            paths.append(a)
    if not paths:
        print(f"Nessun PAPP_Export*.csv trovato in {targets}.")
        return
    print(f"Importo {len(paths)} file di feature:")
    for p in sorted(set(paths)):
        await import_file(p)
    async with AsyncSession() as session:
        total = (await session.execute(select(func.count(MarketFeature.id)))).scalar()
        syms = (
            await session.execute(
                select(MarketFeature.symbol).distinct()
            )
        ).scalars().all()
    print(f"Fatto. {total} barre totali nel DB; simboli: {sorted(s for s in syms if s)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
