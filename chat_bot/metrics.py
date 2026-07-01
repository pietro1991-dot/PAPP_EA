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

from sqlalchemy import select, func, desc, case, extract, or_

from db import AsyncSession, Signal, AccountSnapshot, BacktestTrade, MarketFeature, EaState, MarketSnapshot


def _scope_user(q, col, user_id, owner_id):
    """Filtra per tenant i dati di conto/segnali. user_id None = vista globale
    (riassunto condiviso). Owner e modalità demo vedono anche i dati condivisi."""
    if user_id is None:
        return q
    if owner_id is None or user_id == owner_id:
        return q.where(or_(col == user_id, col.is_(None)))
    return q.where(col == user_id)


async def _market_block(session, symbol: str) -> list[str]:
    """Stato di mercato per un simbolo: ultima barra + confronto con la storia."""
    last = (
        await session.execute(
            select(MarketFeature)
            .where(MarketFeature.symbol == symbol)
            .order_by(desc(MarketFeature.t))
            .limit(1)
        )
    ).scalar_one_or_none()
    if not last:
        return []
    avgs = (
        await session.execute(
            select(
                func.avg(MarketFeature.volatility),
                func.avg(MarketFeature.cluster),
                func.avg(MarketFeature.velocity),
                func.avg(MarketFeature.accel),
            ).where(MarketFeature.symbol == symbol)
        )
    ).first()
    total = (
        await session.execute(
            select(func.count(MarketFeature.id)).where(MarketFeature.symbol == symbol)
        )
    ).scalar() or 1

    async def pct(col, val):
        if val is None:
            return None
        c = (
            await session.execute(
                select(func.count(MarketFeature.id)).where(
                    MarketFeature.symbol == symbol, col <= val
                )
            )
        ).scalar() or 0
        return c / total * 100

    def lvl(p):
        if p is None:
            return ""
        return "alto" if p >= 70 else "basso" if p <= 30 else "nella media"

    lines = [f"{symbol} (ultima barra {last.t.date() if last.t else '?'}): close {last.close:.5f}" if last.close else symbol]
    pos = []
    if last.d_ma30 is not None:
        pos.append(("sopra" if last.d_ma30 > 0 else "sotto") + " MA30")
    if last.d_ma365 is not None:
        pos.append(("sopra" if last.d_ma365 > 0 else "sotto") + " MA365")
    if pos:
        lines.append("  Prezzo: " + ", ".join(pos))
    if last.volatility is not None:
        vp = await pct(MarketFeature.volatility, last.volatility)
        lines.append(
            f"  Volatilità {last.volatility:.2f} (media storica {float(avgs[0] or 0):.2f}, "
            f"{vp:.0f}° percentile → {lvl(vp)})"
        )
    if last.cluster is not None:
        cp = await pct(MarketFeature.cluster, last.cluster)
        lines.append(
            f"  Cluster {last.cluster:.2f} (media {float(avgs[1] or 0):.2f}, {cp:.0f}° perc → {lvl(cp)})"
        )
    extra = []
    if last.velocity is not None:
        extra.append(f"Velocità {last.velocity:.2f}")
    if last.accel is not None:
        extra.append(f"Accelerazione {last.accel:.2f}")
    if last.order_score is not None:
        extra.append(f"OrderScore {last.order_score:.1f}")
    if extra:
        lines.append("  " + " · ".join(extra))
    return lines


def _pnl(v):
    return float(v) if v is not None else 0.0


async def build_digest(symbol: str = "", user_id: int | None = None, owner_id: int | None = None) -> dict:
    """Ritorna {text, sig, recent_count}. `sig` è la firma per la cache: cambia
    quando arriva un nuovo segnale o un nuovo snapshot conto (dati freschi) ed è
    distinta per utente (no cache condivisa tra tenant diversi)."""
    sym = symbol or None
    parts: list[str] = []

    def scope_sig(q):
        return _scope_user(q, Signal.user_id, user_id, owner_id)

    async with AsyncSession() as session:
        last_sig = (await session.execute(select(func.max(Signal.id)))).scalar() or 0
        last_acc = (await session.execute(select(func.max(AccountSnapshot.id)))).scalar() or 0

        # ---------- STATO CONTO ----------
        acc_rows = (
            await session.execute(
                _scope_user(select(AccountSnapshot), AccountSnapshot.user_id, user_id, owner_id)
                .order_by(desc(AccountSnapshot.id)).limit(300)
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
        q = scope_sig(q)
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
        qp = scope_sig(qp)
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
            return (await session.execute(scope_sig(qq))).first()

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
        qr = scope_sig(qr)
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

        # ---------- STORICO BACKTEST ----------
        bt_filter = [BacktestTrade.exit_time.isnot(None)]
        if sym:
            bt_filter.append(BacktestTrade.symbol == sym)
        bt_total = (
            await session.execute(
                select(
                    func.count(BacktestTrade.id),
                    func.coalesce(func.sum(BacktestTrade.pnl_pt), 0),
                    func.coalesce(func.sum(BacktestTrade.pnl_money), 0),
                    func.sum(case((BacktestTrade.pnl_pt > 0, 1), else_=0)),
                ).where(*bt_filter)
            )
        ).first()
        if bt_total and bt_total[0]:
            n, ptot, mtot, w = bt_total
            wr = (w or 0) / n * 100
            parts.append("\n=== STORICO BACKTEST ===")
            parts.append(
                f"Totale: {n} trade, win rate {wr:.0f}%, "
                f"PnL {float(ptot):+.1f}pt ({float(mtot):+.2f} valuta)"
            )
            yr = (
                await session.execute(
                    select(
                        extract("year", BacktestTrade.exit_time).label("y"),
                        func.count(BacktestTrade.id),
                        func.coalesce(func.sum(BacktestTrade.pnl_pt), 0),
                        func.sum(case((BacktestTrade.pnl_pt > 0, 1), else_=0)),
                    )
                    .where(*bt_filter)
                    .group_by("y")
                    .order_by("y")
                )
            ).all()
            for y, c, ptt, ww in yr:
                wry = (ww or 0) / c * 100 if c else 0
                parts.append(f"  {int(y)}: {c} trade, win {wry:.0f}%, PnL {float(ptt):+.1f}pt")

        # ---------- STATO MERCATO (feature indicatore) ----------
        feat_syms = (
            await session.execute(
                select(MarketFeature.symbol).where(MarketFeature.symbol.isnot(None)).distinct()
            )
        ).scalars().all()
        feat_syms = sorted(s for s in feat_syms if s)
        if feat_syms:
            parts.append("\n=== STATO MERCATO (feature indicatore) ===")
            targets = [sym] if sym and sym in feat_syms else feat_syms
            for s in targets:
                parts += await _market_block(session, s)

        # Stato strategie Reversione (oscillatore: "dove siamo" tra un trade e l'altro)
        st_syms = sorted(set(
            (await session.execute(
                select(EaState.symbol).where(EaState.symbol.isnot(None)).distinct()
            )).scalars().all()
        ))
        st_targets = [sym] if (sym and sym in st_syms) else st_syms
        st_lines = []
        for s in st_targets:
            row = (await session.execute(
                _scope_user(select(EaState).where(EaState.symbol == s), EaState.user_id, user_id, owner_id)
                .order_by(desc(EaState.id)).limit(1)
            )).scalar_one_or_none()
            if row is not None:
                oscs = f"{row.osc:.0f}/100" if row.osc is not None else "?"
                extra = []
                if row.dist is not None:
                    extra.append(f"distanza dalla media {row.dist:+.2f}%")
                if row.vol is not None:
                    extra.append(f"volatilità cross {row.vol:.2f}%")
                if row.to_buy is not None and row.to_sell is not None:
                    if row.to_buy <= row.to_sell:
                        extra.append(f"manca {row.to_buy:.0f} (osc) al BUY")
                    else:
                        extra.append(f"manca {row.to_sell:.0f} (osc) al SELL")
                if row.bars_out:
                    extra.append(f"{row.bars_out} barre in banda estrema")
                line = f"  {s}: oscillatore {oscs}" + (f" — {row.info}" if row.info else "")
                if extra:
                    line += " · " + ", ".join(extra)
                st_lines.append(line)
        if st_lines:
            parts.append("\n=== STATO STRATEGIE REVERSIONE (dove siamo ora) ===")
            parts += st_lines

        # Prezzi LIVE: ultimo MarketSnapshot (bid/ask) per simbolo - piu' fresco delle feature
        px = (await session.execute(
            _scope_user(select(MarketSnapshot), MarketSnapshot.user_id, user_id, owner_id)
            .order_by(desc(MarketSnapshot.id)).limit(60)
        )).scalars().all()
        seen_px = {}
        for r in px:
            if r.symbol not in seen_px:
                seen_px[r.symbol] = r
        px_targets = [sym] if (sym and sym in seen_px) else sorted(seen_px)
        px_lines = []
        for s in px_targets:
            r = seen_px.get(s)
            if r is not None and r.bid:
                sp = f" (spread {r.spread_pts:.0f} pt)" if r.spread_pts is not None else ""
                px_lines.append(f"  {s}: bid {r.bid:.5f} / ask {r.ask:.5f}{sp}")
        if px_lines:
            parts.append("\n=== PREZZI LIVE (ultimo tick ricevuto) ===")
            parts += px_lines

    return {
        "text": "\n".join(parts),
        "sig": f"u{user_id if user_id is not None else 'all'}:{symbol or 'all'}:s{last_sig}:a{last_acc}",
        "recent_count": len(recent),
    }
