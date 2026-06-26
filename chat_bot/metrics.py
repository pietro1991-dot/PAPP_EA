"""Toolbox di metriche: calcola dal DB TUTTO ciò che serve all'assistente, così
le risposte sui numeri sono esatte (niente allucinazioni). Il risultato è un
"digest" testuale completo iniettato nel contesto dell'LLM — l'assistente legge
dati già calcolati e si limita a spiegarli.

Sezioni del digest:
  - Stato conto (balance/equity/margine + P/L flottante per simbolo)
  - Performance per simbolo (operazioni chiuse: conteggio, win rate, PnL)
  - Performance per pattern
  - Periodo (oggi, ultimi 7 giorni)
  - Ultimi segnali con setup
"""
from datetime import datetime, timedelta

from sqlalchemy import select, func, desc, case

from db import AsyncSession, Signal, AccountSnapshot


def _pnl(v):
    return float(v) if v is not None else 0.0


async def build_digest(symbol: str = "") -> dict:
    """Ritorna {text, sig, recent_count}. `sig` è la firma per la cache: cambia
    quando arriva un nuovo segnale o un nuovo snapshot conto (dati freschi)."""
    sym = symbol or None
    parts: list[str] = []

    async with AsyncSession() as session:
        last_sig = (await session.execute(select(func.max(Signal.id)))).scalar() or 0
        last_acc = (await session.execute(select(func.max(AccountSnapshot.id)))).scalar() or 0

        # ---------- STATO CONTO ----------
        acc_rows = (
            await session.execute(
                select(AccountSnapshot).order_by(desc(AccountSnapshot.id)).limit(300)
            )
        ).scalars().all()
        parts.append("=== STATO CONTO ===")
        if acc_rows:
            a = acc_rows[0]
            parts.append(
                f"Balance {_pnl(a.balance):.2f} | Equity {_pnl(a.equity):.2f} | "
                f"P/L flottante {_pnl(a.profit):+.2f} | Margine libero {_pnl(a.free_margin):.2f} | "
                f"Livello margine {_pnl(a.margin_level):.0f}%"
            )
            per = {}
            for r in acc_rows:
                if r.symbol and r.symbol not in per:
                    per[r.symbol] = r
            if per:
                seg = ", ".join(
                    f"{s} {_pnl(p.sym_profit):+.2f} ({_pnl(p.sym_pct):+.2f}%, {p.sym_open or 0} aperte)"
                    for s, p in sorted(per.items())
                )
                parts.append("P/L flottante per simbolo: " + seg)
        else:
            parts.append("(nessuno snapshot conto ancora disponibile)")

        # ---------- PERFORMANCE PER SIMBOLO (chiuse) ----------
        q = (
            select(
                Signal.symbol,
                func.count(Signal.id),
                func.coalesce(func.sum(Signal.pnl_pt), 0),
                func.coalesce(func.avg(Signal.pnl_pt), 0),
                func.sum(case((Signal.pnl_pt > 0, 1), else_=0)),
            )
            .where(Signal.action == "close")
        )
        if sym:
            q = q.where(Signal.symbol == sym)
        rows = (await session.execute(q.group_by(Signal.symbol))).all()
        parts.append("\n=== PERFORMANCE PER SIMBOLO (operazioni chiuse) ===")
        if rows and any(r[1] for r in rows):
            tot_c = tot_p = 0
            for s, c, tp, ap, w in rows:
                if not c:
                    continue
                wr = (w or 0) / c * 100
                parts.append(
                    f"{s or '?'}: {c} chiuse, win rate {wr:.0f}%, "
                    f"PnL totale {_pnl(tp):+.1f}pt, media {_pnl(ap):+.1f}pt"
                )
                tot_c += c
                tot_p += _pnl(tp)
            if not sym and tot_c:
                parts.append(f"TOTALE: {tot_c} chiuse, PnL {tot_p:+.1f}pt")
        else:
            parts.append("(nessuna operazione chiusa ancora)")

        # ---------- PERFORMANCE PER PATTERN (chiuse) ----------
        qp = (
            select(
                Signal.symbol,
                Signal.pattern,
                func.count(Signal.id),
                func.coalesce(func.sum(Signal.pnl_pt), 0),
                func.sum(case((Signal.pnl_pt > 0, 1), else_=0)),
            )
            .where(Signal.action == "close")
        )
        if sym:
            qp = qp.where(Signal.symbol == sym)
        prows = (
            await session.execute(
                qp.group_by(Signal.symbol, Signal.pattern).order_by(Signal.symbol, Signal.pattern)
            )
        ).all()
        if prows:
            parts.append("\n=== PERFORMANCE PER PATTERN (chiuse) ===")
            for s, p, c, tp, w in prows:
                if not c:
                    continue
                wr = (w or 0) / c * 100
                parts.append(f"{s or '?'} P{p}: {c} chiuse, win {wr:.0f}%, PnL {_pnl(tp):+.1f}pt")

        # ---------- PERIODO ----------
        now = datetime.utcnow()
        day0 = datetime(now.year, now.month, now.day)
        week0 = now - timedelta(days=7)

        async def period(since):
            qq = select(
                func.count(Signal.id), func.coalesce(func.sum(Signal.pnl_pt), 0)
            ).where(Signal.action == "close", Signal.t >= since)
            if sym:
                qq = qq.where(Signal.symbol == sym)
            return (await session.execute(qq)).first()

        td = await period(day0)
        wk = await period(week0)
        parts.append("\n=== PERIODO ===")
        parts.append(
            f"Oggi: {td[0]} chiuse, PnL {_pnl(td[1]):+.1f}pt. "
            f"Ultimi 7 giorni: {wk[0]} chiuse, PnL {_pnl(wk[1]):+.1f}pt."
        )

        # ---------- ULTIMI SEGNALI ----------
        qr = select(Signal).order_by(desc(Signal.id))
        if sym:
            qr = qr.where(Signal.symbol == sym)
        recent = (await session.execute(qr.limit(12))).scalars().all()
        parts.append("\n=== ULTIMI SEGNALI ===")
        if recent:
            for s in recent:
                line = f"[{s.action}] {s.symbol or '?'} P{s.pattern} {s.dir or ''}"
                if s.entry:
                    line += f" @{s.entry:.5f}"
                if s.pnl_pt is not None:
                    line += f" pnl={s.pnl_pt:+.1f}pt"
                if s.reason:
                    line += f" — {s.reason}"
                parts.append(line)
        else:
            parts.append("(nessun segnale registrato)")

    return {
        "text": "\n".join(parts),
        "sig": f"{symbol or 'all'}:s{last_sig}:a{last_acc}",
        "recent_count": len(recent),
    }
