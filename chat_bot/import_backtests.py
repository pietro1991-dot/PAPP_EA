"""Importa i CSV di backtest generati dall'EA (papp_backtest_<SIMBOLO>.csv) nella
tabella backtest_trades, e genera un documento di analisi per ogni file.

Uso:
    python3 import_backtests.py [cartella]      # default: ../backtests
    python3 import_backtests.py file1.csv ...   # file specifici

Idempotente: re-importare lo stesso file sostituisce i suoi trade (chiave source_file).
Raggruppamento storico per DATA DI USCITA del trade.
"""
import asyncio
import csv
import os
import sys
from datetime import datetime

from sqlalchemy import select, delete, func

from db import AsyncSession, BacktestTrade, init_db

BACKTEST_DIR = os.getenv(
    "BACKTEST_DIR", os.path.join(os.path.dirname(__file__), "..", "backtests")
)


def _parse_dt(s: str):
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


def _i(v):
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def read_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            r = {(k or "").strip(): v for k, v in r.items()}
            rows.append(
                dict(
                    symbol=(r.get("symbol") or "").strip() or None,
                    pattern=_i(r.get("pattern")),
                    dir=(r.get("dir") or "").strip() or None,
                    entry_time=_parse_dt(r.get("entry_time")),
                    entry_price=_f(r.get("entry_price")),
                    exit_time=_parse_dt(r.get("exit_time")),
                    exit_price=_f(r.get("exit_price")),
                    lot=_f(r.get("lot")),
                    pnl_pt=_f(r.get("pnl_pt")),
                    pnl_money=_f(r.get("pnl_money")),
                    reason=(r.get("reason") or "").strip()[:100] or None,
                    duration_d=_f(r.get("duration_d")),
                )
            )
    return rows


async def import_file(path: str):
    fname = os.path.basename(path)
    rows = read_csv(path)
    if not rows:
        print(f"  {fname}: vuoto, saltato")
        return 0
    async with AsyncSession() as session:
        await session.execute(
            delete(BacktestTrade).where(BacktestTrade.source_file == fname)
        )
        for r in rows:
            session.add(BacktestTrade(source_file=fname, **r))
        await session.commit()
    write_analysis(path, rows)
    print(f"  {fname}: {len(rows)} trade importati + analisi generata")
    return len(rows)


def write_analysis(path: str, rows: list[dict]):
    """Genera un documento markdown: riepiloghi per anno/mese + ogni singolo trade."""
    sym = rows[0]["symbol"] or "?"
    closed = [r for r in rows if r["exit_time"] and r["pnl_pt"] is not None]
    out = os.path.join(os.path.dirname(path), f"ANALISI_{sym}.md")

    def agg(items):
        n = len(items)
        wins = sum(1 for x in items if (x["pnl_pt"] or 0) > 0)
        pt = sum(x["pnl_pt"] or 0 for x in items)
        money = sum(x["pnl_money"] or 0 for x in items)
        wr = (wins / n * 100) if n else 0
        return n, wr, pt, money

    lines = [f"# Analisi backtest — {sym}", ""]
    n, wr, pt, money = agg(closed)
    lines += [
        f"**Totale**: {n} trade · Win rate {wr:.0f}% · PnL {pt:+.1f} pt · {money:+.2f} valuta",
        "",
        "## Per anno (data di uscita)",
        "",
        "| Anno | Trade | Win % | PnL pt | PnL valuta |",
        "|---|---|---|---|---|",
    ]
    by_year = {}
    for r in closed:
        by_year.setdefault(r["exit_time"].year, []).append(r)
    for y in sorted(by_year):
        n, wr, pt, money = agg(by_year[y])
        lines.append(f"| {y} | {n} | {wr:.0f}% | {pt:+.1f} | {money:+.2f} |")

    lines += ["", "## Per mese", "", "| Mese | Trade | Win % | PnL pt |", "|---|---|---|---|"]
    by_month = {}
    for r in closed:
        key = r["exit_time"].strftime("%Y-%m")
        by_month.setdefault(key, []).append(r)
    for m in sorted(by_month):
        n, wr, pt, _ = agg(by_month[m])
        lines.append(f"| {m} | {n} | {wr:.0f}% | {pt:+.1f} |")

    lines += [
        "",
        "## Ogni trade",
        "",
        "| # | Pattern | Dir | Ingresso | Uscita | PnL pt | PnL val | Durata | Motivo |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(sorted(closed, key=lambda x: x["exit_time"]), 1):
        et = r["entry_time"].strftime("%Y-%m-%d") if r["entry_time"] else "?"
        xt = r["exit_time"].strftime("%Y-%m-%d") if r["exit_time"] else "?"
        lines.append(
            f"| {i} | P{r['pattern']} | {r['dir']} | {et} | {xt} | "
            f"{(r['pnl_pt'] or 0):+.1f} | {(r['pnl_money'] or 0):+.2f} | "
            f"{(r['duration_d'] or 0):.0f}g | {r['reason'] or ''} |"
        )
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


async def main(args):
    await init_db()
    paths = []
    if args:
        for a in args:
            if os.path.isdir(a):
                paths += [os.path.join(a, f) for f in os.listdir(a) if f.endswith(".csv")]
            elif a.endswith(".csv"):
                paths.append(a)
    else:
        d = BACKTEST_DIR
        if os.path.isdir(d):
            paths = [os.path.join(d, f) for f in os.listdir(d) if f.startswith("papp_backtest") and f.endswith(".csv")]
    if not paths:
        print(f"Nessun CSV di backtest trovato in {BACKTEST_DIR} (o argomenti).")
        return
    print(f"Importo {len(paths)} file:")
    tot = 0
    for p in sorted(paths):
        tot += await import_file(p)
    async with AsyncSession() as session:
        total = (await session.execute(select(func.count(BacktestTrade.id)))).scalar()
    print(f"Fatto. {tot} trade importati in questa sessione; {total} totali nel DB.")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
