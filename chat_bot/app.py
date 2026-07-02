import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta

from sqlalchemy import select, desc, delete, extract, case, or_, func as sa_func

from db import (
    EaState,
    EquityPoint,
    PriceBar,
    init_db,
    AsyncSession,
    Signal,
    ChatHistory,
    MarketSnapshot,
    User,
    DailySummary,
    AccountSnapshot,
    Conversation,
    PushSubscription,
    BacktestTrade,
    MarketFeature,
    LicenseKey,
    Lead,
)
from mt5_bridge import LogTailer
import llm_worker
import auth
import metrics
import notifications
import licensing
import entitlements
import catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("papp")

# WebSocket connessi: mappa ws -> user_id (None se non identificato). Serve per
# inviare ogni segnale SOLO ai socket del cliente a cui appartiene (multi-tenant).
clients: dict[WebSocket, int | None] = {}

# Utente "proprietario" (il tuo conto, via bridge locale). Se impostato, i dati del
# bridge vengono taggati con questo id e i clienti vedono SOLO i propri dati (vera
# isolazione). Se non impostato → modalità demo: i dati senza user_id sono condivisi.
def _owner_id():
    v = os.getenv("EA_OWNER_USER_ID", "").strip()
    return int(v) if v.isdigit() else None


SUMMARY_REFRESH_MIN = int(os.getenv("SUMMARY_REFRESH_MIN", "30"))

EA_CONFIG_FILE = os.getenv("EA_CONFIG_FILE", os.path.join(os.path.dirname(__file__), "ea_config.json"))


def _load_ea_config():
    """Configurazione strategia centralizzata (modificabile senza riavvio)."""
    try:
        with open(EA_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"default": {"enabled": True, "risk": 10}, "symbols": {}}


# --- Report MT5 originali (HTML + grafici) archiviati in backtests/ReportTester_<SIM>_* ---
BACKTESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "backtests")


def _report_dir(symbol: str):
    """Cartella del report MT5 per il simbolo, o None."""
    import glob
    for d in sorted(glob.glob(os.path.join(BACKTESTS_DIR, f"ReportTester_{symbol.upper()}_*"))):
        if os.path.isdir(d):
            return d
    return None


def _symbol_reports() -> dict:
    """{SIMBOLO: url_html} per i simboli con un report MT5 archiviato."""
    import glob, re
    out: dict = {}
    for d in sorted(glob.glob(os.path.join(BACKTESTS_DIR, "ReportTester_*"))):
        m = re.search(r"ReportTester_([A-Z]{6})", os.path.basename(d))
        if not (m and os.path.isdir(d)):
            continue
        htmls = glob.glob(os.path.join(d, "*.html"))
        if htmls:
            out.setdefault(m.group(1), f"/api/public/report/{m.group(1)}/{os.path.basename(htmls[0])}")
    return out


def _scope(q, col, user: User):
    """Filtra una query per tenant: ogni utente vede i propri dati. L'owner (e la
    modalità demo senza owner) vede anche i dati condivisi (user_id NULL)."""
    oid = _owner_id()
    if oid is None or user.id == oid:
        return q.where(or_(col == user.id, col.is_(None)))
    return q.where(col == user.id)


async def _user_plan(user: User) -> str:
    """Piano EFFETTIVO dell'utente ('starter'|'pro'|'elite'), '' se nessuno o
    abbonamento non valido (revocato/inattivo/scaduto). Così uno scaduto perde
    gli accessi (segnali/EA/chatbot tornano al livello demo).
    L'OWNER ha accesso pieno a prescindere dalla licenza (è l'admin del prodotto)."""
    oid = _owner_id()
    if oid is not None and getattr(user, "id", None) == oid:
        return "portfolio"      # owner: tutti gli EA + segnali + assistente premium
    if not getattr(user, "license_key", None):
        return ""
    async with AsyncSession() as session:
        lk = (
            await session.execute(select(LicenseKey).where(LicenseKey.key == user.license_key))
        ).scalar_one_or_none()
    if not lk or lk.revoked or lk.active is False:
        return ""
    if lk.expires_at is not None and lk.expires_at < datetime.utcnow():
        return ""
    return (lk.plan or "").lower()


async def _user_tier(user: User) -> str:
    """Tier LLM dal piano (free/paid/premium): quale modello usa l'assistente."""
    return entitlements.chatbot_tier(await _user_plan(user))


# Tetto giornaliero di messaggi per il tier FREE: protegge la quota gratuita condivisa
# e spinge all'upgrade. 0 = illimitato. Le domande comuni precalcolate non contano.
FREE_DAILY_MSGS = int(os.getenv("FREE_DAILY_MSGS", "5"))


async def _free_msgs_used_today(user_id: int) -> int:
    """Messaggi del free-user da mezzanotte locale. Le domande comuni precalcolate
    bypassano comunque il controllo (vengono sempre risposte, 0 quota LLM)."""
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    async with AsyncSession() as session:
        n = (await session.execute(
            select(sa_func.count(ChatHistory.id)).where(
                ChatHistory.user_id == user_id,
                ChatHistory.created_at >= since,
            )
        )).scalar()
    return n or 0

# Domande "comuni" servite dal riassunto condiviso precalcolato (0 quota LLM).
COMMON_KEYWORDS = (
    "come va", "come sta andando", "com'è andata", "comè andata",
    "riassunto", "riassumi", "andamento", "performance", "come è andata",
    "bilancio", "situazione",
)


def _is_common_question(q: str) -> bool:
    ql = q.lower()
    return any(k in ql for k in COMMON_KEYWORDS)


async def _build_context(symbol: str = ""):
    """Contesto condiviso (segnali recenti + statistiche) usato sia dalla chat sia
    dal riassunto. Se `symbol` è valorizzato, filtra su quel simbolo.
    Ritorna (context_str, last_signal_id, recent_count)."""
    async with AsyncSession() as session:
        rq = select(Signal).order_by(desc(Signal.id))
        if symbol:
            rq = rq.where(Signal.symbol == symbol)
        recent = (await session.execute(rq.limit(20))).scalars().all()

        sq = select(
            sa_func.count(Signal.id),
            sa_func.coalesce(sa_func.sum(Signal.pnl_pt), 0),
        ).where(Signal.action == "close")
        if symbol:
            sq = sq.where(Signal.symbol == symbol)
        stats = (await session.execute(sq)).first()

    scope = f" ({symbol})" if symbol else ""
    ctx_lines = [f"Segnali recenti{scope} (ultimi 20):"]
    for s in recent[:10]:
        line = f"[{s.action}] {s.symbol or '?'} pattern={s.pattern} dir={s.dir}"
        if s.reason:
            line += f" reason={s.reason}"
        if s.pnl_pt is not None:
            line += f" pnl={s.pnl_pt:+.1f}pt"
        if s.entry:
            line += f" entry={s.entry:.5f}"
        ctx_lines.append(line)
    if stats:
        ctx_lines.append(f"Totali: {stats[0]} chiusure, PnL={float(stats[1]):+.1f}pt")

    last_id = recent[0].id if recent else 0
    return "\n".join(ctx_lines), last_id, len(recent)


async def _generate_perf_summary():
    """Genera UNA volta il riassunto della performance e lo salva: servito a tutti
    gli utenti senza ulteriori chiamate LLM."""
    digest = await metrics.build_digest()
    if digest["recent_count"] == 0:
        return
    question = (
        "Riassumi in massimo 3 frasi l'andamento della strategia oggi: numero di "
        "operazioni, PnL complessivo e il pattern più attivo."
    )
    answer = await llm_worker.submit(question, digest["text"], "summary:" + digest["sig"])
    if answer and answer not in (llm_worker.FALLBACK, llm_worker.BUSY, llm_worker.RATE):
        async with AsyncSession() as session:
            session.add(DailySummary(kind="perf_today", content=answer))
            await session.commit()
        log.info("Riassunto performance aggiornato")


async def _summary_loop():
    while True:
        try:
            await _generate_perf_summary()
        except Exception:
            log.exception("Errore generazione riassunto")
        await asyncio.sleep(SUMMARY_REFRESH_MIN * 60)


_REPORT_HOURS = {"morning": 8, "evening": 20}   # ora locale del server (GMT+1)


async def _generate_scheduled_report(kind: str):
    """Resoconto mattina/sera ELABORATO DALL'LLM, salvato e inviato via push a tutti gli iscritti."""
    digest = await metrics.build_digest()   # globale: stato di mercato live + segnali del giorno
    if kind == "morning":
        q = ("Sei l'assistente PHAI. Scrivi il RESOCONTO DEL MATTINO in italiano, massimo 4 frasi: "
             "come si apre la giornata sui simboli seguiti. Usa lo stato di mercato (regime calmo o agitato, "
             "posizione del prezzo rispetto alle medie) e di' come sono posizionati gli edge validati "
             "(es. la reversione vive nel regime calmo; il Motore Base segue la struttura del prezzo). "
             "NON predire la direzione e NON dire 'compra/vendi': descrivi il contesto e cosa osservano i sistemi.")
        title = "☀️ PHAI · Resoconto del mattino"
    else:
        q = ("Sei l'assistente PHAI. Scrivi il RESOCONTO DELLA SERA in italiano, massimo 3 frasi: "
             "com'è andata la giornata — numero di operazioni, PnL complessivo e il pattern più attivo. "
             "Tono sintetico, concreto e onesto.")
        title = "🌙 PHAI · Resoconto della sera"
    answer = await llm_worker.submit(q, digest["text"], f"{kind}:{digest['sig']}")
    if not answer or answer in (llm_worker.FALLBACK, llm_worker.BUSY, llm_worker.RATE):
        return
    async with AsyncSession() as session:
        session.add(DailySummary(kind=kind, content=answer))
        await session.commit()
    try:
        await notifications.dispatch(title, answer[:170], tag=f"report-{kind}", url="/")
    except Exception:
        log.exception("Push resoconto %s fallita", kind)
    log.info("Resoconto %s generato e notificato", kind)


async def _scheduled_reports_loop():
    """Genera il resoconto del mattino (08:00) e della sera (20:00), ora locale del server."""
    last_fired: dict[str, str] = {}
    while True:
        try:
            now = datetime.now()
            today = now.date().isoformat()
            for kind, hour in _REPORT_HOURS.items():
                if now.hour == hour and last_fired.get(kind) != today:
                    last_fired[kind] = today
                    await _generate_scheduled_report(kind)
        except Exception:
            log.exception("Errore loop resoconti")
        await asyncio.sleep(300)   # ricontrolla ogni 5 minuti


async def _latest_summary(kind: str = "perf_today"):
    async with AsyncSession() as session:
        row = (
            await session.execute(
                select(DailySummary)
                .where(DailySummary.kind == kind)
                .order_by(desc(DailySummary.id))
                .limit(1)
            )
        ).scalar_one_or_none()
    return row.content if row else None


async def _broadcast(payload: dict, user_id: int | None):
    """Invia il payload via WS solo ai socket del tenant giusto (o a tutti se il
    dato è condiviso / in modalità demo)."""
    oid = _owner_id()
    dead = []
    for ws, uid in list(clients.items()):
        visible = (uid == user_id) or (
            user_id is None and (oid is None or uid == oid)
        )
        if not visible:
            continue
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.pop(ws, None)


async def _signal_subscriber_ids() -> "set[int]":
    """user_id degli utenti con un piano che dà diritto ai SEGNALI e licenza attiva.
    Le push dei segnali vanno SOLO a questi (abbonati paganti)."""
    now = datetime.utcnow()
    async with AsyncSession() as session:
        rows = (
            await session.execute(
                select(
                    User.id, LicenseKey.plan, LicenseKey.active,
                    LicenseKey.revoked, LicenseKey.expires_at,
                ).join(LicenseKey, LicenseKey.key == User.license_key)
            )
        ).all()
    ids: set[int] = set()
    for uid, plan, active, revoked, exp in rows:
        if revoked or active is False:
            continue
        if exp is not None and exp < now:
            continue
        if entitlements.can_signals(plan):
            ids.add(uid)
    return ids


async def _signal_recipients(user_id: int | None) -> "set[int]":
    """Destinatari della push di un segnale, COERENTI con lo scoping della dashboard
    (_broadcast). Il feed master/owner va a tutti gli abbonati ai segnali; il segnale
    del conto di un cliente va SOLO a quel cliente (niente leak tra tenant)."""
    oid = _owner_id()
    if user_id is None or user_id == oid:
        return await _signal_subscriber_ids()
    return {user_id}


# Campione storico equity (grafico "andamento conto"): 1/ora per utente, bounded.
EQUITY_SAMPLE_SEC = int(os.getenv("EQUITY_SAMPLE_SEC", "3300"))       # ~1 ora tra i campioni
EQUITY_RETENTION_DAYS = int(os.getenv("EQUITY_RETENTION_DAYS", "90"))  # quanti giorni tenere
_equity_last: dict = {}   # user_id -> ultimo campionamento (throttle in memoria, no query extra)


async def _upsert_latest(session, Model, user_id, symbol, fields: dict):
    """Stato LIVE scalabile: tiene UNA sola riga per (user_id, symbol). Aggiorna la
    piu' recente coi valori freschi e cancella eventuali duplicati piu' vecchi, così
    lo spazio resta FISSO (non cresce ogni 15s). NON tocca trade/chat/backtest."""
    row = (await session.execute(
        select(Model).where(Model.user_id == user_id, Model.symbol == symbol)
        .order_by(desc(Model.t)).limit(1)
    )).scalar_one_or_none()
    if row is None:
        session.add(Model(user_id=user_id, symbol=symbol, **fields))
    else:
        for k, v in fields.items():
            setattr(row, k, v)
        await session.execute(
            delete(Model).where(
                Model.user_id == user_id, Model.symbol == symbol, Model.id != row.id
            )
        )


async def process_event(data: dict, user_id: int | None = None):
    """Ingestione di un evento dell'EA (da bridge locale o da /api/ea/ingest),
    taggato con il tenant `user_id`. Gestisce account, market e segnali."""
    if data.get("action") == "account":
        async with AsyncSession() as session:
            await _upsert_latest(session, AccountSnapshot, user_id, data.get("symbol") or "?", dict(
                t=data.get("t"),
                balance=data.get("balance"), equity=data.get("equity"),
                margin=data.get("margin"), free_margin=data.get("free_margin"),
                margin_level=data.get("margin_level"), profit=data.get("profit"),
                sym_profit=data.get("sym_profit"), sym_pct=data.get("sym_pct"),
                sym_open=data.get("sym_open"),
            ))
            # campione storico equity 1/ora (throttle in memoria) + retention -> spazio bounded
            eq = data.get("equity")
            if eq is not None:
                now = datetime.now()
                last = _equity_last.get(user_id)
                if last is None or (now - last).total_seconds() >= EQUITY_SAMPLE_SEC:
                    _equity_last[user_id] = now
                    session.add(EquityPoint(user_id=user_id, t=now,
                                            balance=data.get("balance"), equity=eq))
                    await session.execute(delete(EquityPoint).where(
                        EquityPoint.user_id == user_id,
                        EquityPoint.t < now - timedelta(days=EQUITY_RETENTION_DAYS),
                    ))
            await session.commit()
        return

    if data.get("action") == "market":
        async with AsyncSession() as session:
            await _upsert_latest(session, MarketSnapshot, user_id, data.get("symbol") or "EURUSD", dict(
                t=data.get("t"), bid=data.get("bid"), ask=data.get("ask"),
                spread_pts=data.get("spread_pts"),
            ))
            await session.commit()
        return

    if data.get("action") == "bars":
        # Barre OHLC (D1) del cross: GLOBALI per simbolo (prezzo uguale per tutti), upsert per (symbol, t).
        sym = (data.get("symbol") or "").upper()
        bars = data.get("bars") or []
        if not sym or not bars:
            return
        async with AsyncSession() as session:
            for b in bars[-400:]:
                tv = b.get("t")
                if isinstance(tv, (int, float)):
                    tv = datetime.fromtimestamp(tv)
                if tv is None:
                    continue
                existing = (await session.execute(
                    select(PriceBar).where(PriceBar.symbol == sym, PriceBar.t == tv).limit(1)
                )).scalar_one_or_none()
                if existing is not None:
                    existing.o, existing.h, existing.l, existing.c = b.get("o"), b.get("h"), b.get("l"), b.get("c")
                else:
                    session.add(PriceBar(symbol=sym, t=tv, o=b.get("o"), h=b.get("h"), l=b.get("l"), c=b.get("c")))
            await session.commit()
        return

    if data.get("action") == "features":
        # Feature di mercato (Volatilità/Cluster/…) pushate dall'EA leggendo PHAI_Median.
        # Globali per simbolo (non per-tenant). Idempotente per barra: piu' client non duplicano.
        async with AsyncSession() as session:
            sym = data.get("symbol") or "EURUSD"
            tval = data.get("t")
            existing = None
            if tval is not None:
                existing = (await session.execute(
                    select(MarketFeature).where(
                        MarketFeature.symbol == sym, MarketFeature.t == tval
                    ).limit(1)
                )).scalar_one_or_none()
            vals = dict(
                close=data.get("close"),
                d_med=data.get("d_med"), d_ma30=data.get("d_ma30"), d_ma365=data.get("d_ma365"),
                cluster=data.get("cluster"), velocity=data.get("velocity"),
                accel=data.get("accel"), volatility=data.get("volatility"),
                order_score=data.get("order_score"), spread=data.get("spread"),
            )
            if existing is not None:
                # stessa barra D1 -> aggiorna ai valori freschi (la barra in formazione cambia)
                for k, v in vals.items():
                    setattr(existing, k, v)
            else:
                session.add(MarketFeature(symbol=sym, t=tval, **vals))
            await session.commit()
        return

    if data.get("action") == "state":
        # stato periodico di una strategia (oscillatore + nota): "dove siamo" tra i trade.
        async with AsyncSession() as session:
            await _upsert_latest(session, EaState, user_id, data.get("symbol") or "?", dict(
                t=data.get("t"), osc=data.get("osc"), info=(data.get("info") or "")[:200],
                dist=data.get("dist"), vol=data.get("vol"),
                to_buy=data.get("to_buy"), to_sell=data.get("to_sell"),
                bars_out=data.get("bars_out"),
            ))
            await session.commit()
        return

    async with AsyncSession() as session:
        sig = Signal(
            t=data.get("t"),
            user_id=user_id,
            symbol=data.get("symbol"),
            action=data.get("action", ""),
            pattern=data.get("pattern"),
            dir=data.get("dir"),
            reason=data.get("reason"),
            entry=data.get("entry"),
            sl=data.get("sl"),
            tp=data.get("tp"),
            lot=data.get("lot"),
            exit_price=data.get("exitPrice") or data.get("exit_price"),
            pnl_pt=data.get("pnl") or data.get("pnl_pt"),
        )
        session.add(sig)
        await session.commit()
        await session.refresh(sig)

    payload = {
        "id": sig.id,
        "t": sig.t.isoformat() if sig.t else None,
        "symbol": sig.symbol,
        "action": sig.action,
        "pattern": sig.pattern,
        "dir": sig.dir,
        "reason": sig.reason,
        "entry": sig.entry,
        "sl": sig.sl,
        "tp": sig.tp,
        "lot": sig.lot,
        "exit_price": sig.exit_price,
        "pnl_pt": sig.pnl_pt,
    }
    await _broadcast(payload, user_id)
    log.info("Signal #%d (u=%s): %s p%d %s", sig.id, user_id, sig.action, sig.pattern or 0, sig.dir or "")

    # Notifica push (apertura/chiusura ordine). Esteso facilmente ad altri eventi.
    if sig.action in ("open", "close"):
        sym = sig.symbol or ""
        pat = f"P{sig.pattern}" if sig.pattern is not None else ""
        dirs = sig.dir or ""
        if sig.action == "open":
            verb = "COMPRA" if (dirs or "").upper().startswith("B") or dirs == "1" else ("VENDI" if dirs else "SEGNALE")
            title = f"🟢 {verb} {sym}".strip()
            parts = []
            if sig.entry:
                parts.append(f"Entra @ {sig.entry:.5f}")
            if sig.tp:
                parts.append(f"🎯 TP {sig.tp:.5f}")
            if sig.sl:
                parts.append(f"🛑 SL {sig.sl:.5f}")
            body = " · ".join(parts)
            if not body:
                body = sig.reason or "Nuovo segnale"
        else:
            neg = sig.pnl_pt is not None and sig.pnl_pt < 0
            title = f"{'🔴' if neg else '🟢'} Ordine chiuso — {sym} {pat} {dirs}".strip()
            body = ""
            if sig.pnl_pt is not None:
                body += f"PnL {sig.pnl_pt:+.1f}pt. "
            if sig.reason:
                body += sig.reason
        sub_ids = await _signal_recipients(user_id)
        asyncio.create_task(
            notifications.dispatch(title, body or "Nuovo evento sull'EA", tag=f"sig{sig.id}", user_ids=sub_ids)
        )


async def on_signal(data: dict):
    """Callback del bridge locale: i dati del log locale = conto del proprietario."""
    await process_event(data, _owner_id())


# ---------------------------------------------------------------------------
# API per l'EA dei clienti (autenticate dalla license key, non dal cookie).
# validate = licenza+binding conto+enforcement; ingest = telemetria multi-tenant;
# config = strategia centralizzata. L'EA parla in JSON in ingresso e riceve
# key=value in uscita (facile da parsare in MQL5, senza JSON parser).
# ---------------------------------------------------------------------------
def _kv(d: dict) -> str:
    return "\n".join(f"{k}={'' if v is None else v}" for k, v in d.items()) + "\n"


async def _resolve_license(key: str):
    """Ritorna (LicenseKey, motivo_errore). Valida stato/scadenza."""
    key = (key or "").strip()
    if not key:
        return None, "no_key"
    async with AsyncSession() as session:
        lk = (await session.execute(select(LicenseKey).where(LicenseKey.key == key))).scalar_one_or_none()
    if not lk:
        return None, "invalid"
    if lk.revoked:
        return lk, "revoked"
    if lk.active is False:
        return lk, "inactive"
    if lk.expires_at is not None and lk.expires_at < datetime.utcnow():
        return lk, "expired"
    return lk, ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("DB inizializzato")
    llm_worker.start_worker()
    tailer = LogTailer(on_signal)
    task = asyncio.create_task(tailer.start())
    log.info("LogTailer avviato su: %s/%s", tailer.dir, tailer.PATTERN)
    summary_task = asyncio.create_task(_summary_loop())
    log.info("Loop riassunti avviato (ogni %d min)", SUMMARY_REFRESH_MIN)
    reports_task = asyncio.create_task(_scheduled_reports_loop())
    log.info("Loop resoconti mattina/sera avviato (08:00 / 20:00 ora server)")
    yield
    tailer.stop()
    task.cancel()
    summary_task.cancel()
    reports_task.cancel()
    llm_worker.stop_worker()


app = FastAPI(title="PHAI Chat", version="1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@phai.io")


PAGE_LANGS = ("it", "en", "fr", "es")


def _req_lang(request: Request) -> str:
    """Lingua della pagina: ?lang=… → cookie → Accept-Language → it."""
    q = (request.query_params.get("lang") or "").lower()
    if q in PAGE_LANGS:
        return q
    c = (request.cookies.get("lang") or "").lower()
    if c in PAGE_LANGS:
        return c
    al = (request.headers.get("accept-language", "")[:2]).lower()
    return al if al in ("en", "fr", "es") else "it"


def _lang_selector(cur: str) -> str:
    opts = "".join(
        f'<option value="{c}"{" selected" if c == cur else ""}>{flag} {c.upper()}</option>'
        for c, flag in (("it", "🇮🇹"), ("en", "🇬🇧"), ("fr", "🇫🇷"), ("es", "🇪🇸"))
    )
    return (
        '<div style="position:fixed;bottom:16px;right:16px;z-index:9999;font-family:system-ui">'
        '<select aria-label="Lingua" onchange="(function(v){document.cookie=\'lang=\'+v+\';path=/;max-age=31536000\';'
        'var u=new URL(location);u.searchParams.set(\'lang\',v);location=u})(this.value)" '
        'style="background:#11141b;color:#e9ebf2;border:1px solid #283149;border-radius:10px;'
        'padding:8px 10px;font-size:13px;font-weight:600;cursor:pointer;outline:none;'
        'box-shadow:0 6px 20px rgba(0,0,0,.45)">'
        f'{opts}</select></div>'
    )


def _inject_prices(html: str) -> str:
    """Prezzi DINAMICI: i token {{P_*}} nelle landing diventano i valori di catalog.py.
    Così landing, app ed email restano sempre coerenti: cambi il prezzo in un solo posto."""
    try:
        prices = {
            "P_SINGLE": catalog.SINGLE_PRICE,
            "P_ASSIST": catalog.SIGNALS_PRICE,
            "P_DIF": catalog.PACKS[0]["price"],
            "P_BIL": catalog.PACKS[1]["price"],
            "P_COM": catalog.PACKS[2]["price"],
            "P_AUTO": catalog.PORTFOLIO["price"],
            "P_DFY": catalog.DFY_PRICE,
        }
        for k, v in prices.items():
            html = html.replace("{{" + k + "}}", f"{v:.0f}")
    except Exception:
        pass
    return html


def _serve_page(name: str, request: Request) -> HTMLResponse:
    """Serve la pagina nella lingua del visitatore (file <name>.<lang>.html, fallback IT),
    inietta i PREZZI dinamici (token {{P_*}}) e il selettore lingua."""
    lang = _req_lang(request)
    path = f"templates/{name}.{lang}.html" if lang != "it" else f"templates/{name}.html"
    if not os.path.exists(path):
        path = f"templates/{name}.html"
        lang = "it"
    html_c = _inject_prices(open(path, encoding="utf-8").read())
    html_c = html_c.replace("</body>", _lang_selector(lang) + "</body>", 1)
    resp = HTMLResponse(html_c)
    if (request.query_params.get("lang") or "").lower() in PAGE_LANGS:
        resp.set_cookie("lang", lang, max_age=31536000, samesite="lax")
    return resp


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token and auth.verify_session_token(token):
        return HTMLResponse(
            open("templates/index.html").read(),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
    return _serve_page("landing", request)   # pubblico → landing marketing multilingua


@app.get("/landing", response_class=HTMLResponse)
async def landing_preview(request: Request):
    """Landing marketing SEMPRE visibile (anche da loggato), per poterla rivedere.
    Su '/' invece i loggati vedono la dashboard."""
    return _serve_page("landing", request)


def _public_nav(active=""):
    """Header di navigazione del SITO pubblico (condiviso da landing e /risultati)."""
    items = [("/", "Home", "home"), ("/landing#come-funziona", "Come funziona", "come"),
             ("/risultati", "Risultati", "risultati"), ("/landing#prezzi", "Prezzi", "prezzi"),
             ("/landing#faq", "FAQ", "faq"), ("/demo", "Demo", "demo")]
    links = "".join(
        f'<a class="pn-link{" on" if k == active else ""}" href="{href}">{label}</a>'
        for href, label, k in items
    )
    return (
        '<header class="pubnav"><div class="pn-wrap">'
        '<a class="pn-brand" href="/"><img src="/static/logo-mark.png" alt="PHAI"><b>PHAI <i>TRADING</i></b></a>'
        f'<nav class="pn-links">{links}</nav>'
        '<a class="pn-cta" href="/login">Accedi</a>'
        '</div></header>'
    )


def _equity_svg(d, w=560, h=150):
    ys = sorted(d.get("by_year", []), key=lambda y: y["year"])
    if not ys:
        return ""
    pts = [d["initial_capital"]] + [y["end_capital"] for y in ys]
    n = len(pts); mn = min(pts); mx = max(pts); rng = (mx - mn) or 1; P = 6
    fx = lambda i: P + i * (w - 2 * P) / (n - 1)
    fy = lambda v: h - P - ((v - mn) / rng) * (h - 2 * P)
    line = " ".join(("M" if i == 0 else "L") + f"{fx(i):.1f},{fy(v):.1f}" for i, v in enumerate(pts))
    area = (f"M{fx(0):.1f},{h - P} " + " ".join(f"L{fx(i):.1f},{fy(v):.1f}" for i, v in enumerate(pts))
            + f" L{fx(n - 1):.1f},{h - P} Z")
    col = "#3ddc97" if pts[-1] >= pts[0] else "#f1707b"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="eqsvg">'
            f'<path d="{area}" fill="{col}22"/><path d="{line}" fill="none" stroke="{col}" stroke-width="2.5"/></svg>')


@app.get("/risultati", response_class=HTMLResponse)
async def risultati_page():
    """Pagina PUBBLICA dei risultati: lo showroom degli EA (grafico + cosa fa + CTA),
    visibile senza login. È la prova-in-anticipo: vedi tutto prima di registrarti."""
    def money(v):
        return f"{v:,.0f}".replace(",", ".")
    blocks = []

    async def _ea_card(e):
        d = await _overview_data(e["symbol"]) if e["live"] else None
        has = bool(d and d.get("available"))
        if has:
            tt = d["totals"]
            chart = _equity_svg(d)
            kpis = (
                f'<div class="rk"><b class="{"pos" if tt["cagr_pct"]>=0 else "neg"}">{tt["cagr_pct"]:+.1f}%</b><span>Crescita/anno</span></div>'
                f'<div class="rk"><b>{tt["winrate"]}%</b><span>Win rate</span></div>'
                f'<div class="rk"><b>{tt["trades"]}</b><span>Trade</span></div>'
            )
            cap = (f'<div class="rcap">Capitale {money(d["initial_capital"])}€ → '
                   f'<b>{money(d["initial_capital"]+tt["pnl_money"])}€</b> '
                   f'<span class="rspan">({d["years"]} anni di backtest)</span></div>')
        else:
            chart = ('<div class="rsoon">⚠️ Backtest non ancora disponibile nel database.</div>'
                     if e["live"] else '<div class="rsoon">🔜 In arrivo</div>')
            kpis = ""; cap = ""
        if e.get("flagship"):
            badge = '<span class="rstat live" style="background:#c9a14a;color:#111">★ Best-seller</span>'
        elif not e["live"]:
            badge = '<span class="rstat soon">In arrivo</span>'
        else:
            badge = '<span class="rstat live">Validato</span>'
        if e["live"]:
            cta = (f'<a class="rbtn gold" href="/checkout?sku=single:{e["id"]}">Attiva da {int(catalog.SINGLE_PRICE)}€/mese</a>'
                   f'<a class="rbtn ghost" href="/demo">Vedi nella Demo</a>')
        else:
            cta = '<a class="rbtn ghost" href="/report">Avvisami quando esce</a>'
        eng = catalog.ENGINES.get(e["engine"], {})
        etag = (f'<span class="rtag" style="color:{eng.get("color","#888")};font-weight:700">{catalog.tr(eng.get("name",""))}</span>'
                if eng else '')
        return (
            f'<div class="rcard"><div class="rtop"><div><div class="rname">{e["name"]}</div>'
            f'<div class="rtag">{catalog.tr(e["tagline"])}</div>{etag}</div>{badge}</div>'
            f'{cap}<div class="rchart">{chart}</div><div class="rkpis">{kpis}</div>'
            f'<div class="rsec"><h4>Cosa fa</h4><p>{catalog.tr(e["mechanism"])}</p></div>'
            f'<div class="rsec"><h4>Rischio</h4><p>{catalog.tr(e["risk"])}</p></div>'
            f'<div class="rcta">{cta}</div></div>'
        )

    # 1) l'EROE in evidenza
    hero = next((e for e in catalog.EAS if e.get("flagship")), catalog.EAS[0] if catalog.EAS else None)
    if hero:
        blocks.append('<section class="rengine"><div class="reng-h">'
                      '<span class="reng-nm">🏆 Il nostro cavallo di battaglia</span></div>'
                      f'<div class="rgrid">{await _ea_card(hero)}</div></section>')
    # 2) gli altri singoli
    others = [e for e in catalog.EAS if e is not hero]
    if others:
        cards = [await _ea_card(e) for e in others]
        blocks.append('<section class="rengine"><div class="reng-h">'
                      '<span class="reng-nm">Altri singoli</span></div>'
                      f'<div class="rgrid">{"".join(cards)}</div></section>')
    # 3) i pacchetti (si vendono sul drawdown basso)
    pcards = []
    for p in catalog.PACKS:
        st = p.get("stats") or {}
        stat_html = (f'<div class="rkpis"><div class="rk"><b class="pos">+{st.get("cagr",0):.1f}%</b><span>Crescita/anno</span></div>'
                     f'<div class="rk"><b>{st.get("dd","–")}%</b><span>Max drawdown</span></div>'
                     f'<div class="rk"><b>{len(p["eas"])}</b><span>EA inclusi</span></div></div>') if st else ''
        rec = ' <span class="rstat live">Consigliato</span>' if p.get("recommended") else ''
        pcards.append(
            f'<div class="rcard"><div class="rtop"><div><div class="rname">{catalog.tr(p["name"])}{rec}</div>'
            f'<div class="rtag">{catalog.tr(p["tagline"])}</div></div></div>{stat_html}'
            f'<div class="rcta"><a class="rbtn gold" href="/checkout?sku={p["id"]}">Attiva da {int(p["price"])}€/mese</a></div></div>'
        )
    if pcards:
        blocks.append('<section class="rengine"><div class="reng-h">'
                      '<span class="reng-nm">📦 Pacchetti — più strategie, drawdown più basso</span></div>'
                      f'<div class="rgrid">{"".join(pcards)}</div></section>')
    # 4) piano Assistente + Segnali (senza EA): l'ingresso a più bassa frizione
    a = catalog.ASSISTANT
    feats = "".join(f'<li>{f}</li>' for f in catalog.tr(a["features"]))
    blocks.append('<section class="rengine"><div class="reng-h">'
                  '<span class="reng-nm">🔔 Non vuoi installare un EA? Parti da qui</span></div>'
                  f'<div class="rgrid"><div class="rcard"><div class="rtop"><div>'
                  f'<div class="rname">{catalog.tr(a["name"])}</div>'
                  f'<div class="rtag">{catalog.tr(a["tagline"])}</div></div></div>'
                  f'<ul style="margin:10px 2px;padding-left:18px;line-height:1.85;font-size:13.5px">{feats}</ul>'
                  f'<div class="rcta"><a class="rbtn gold" href="/checkout?sku=signals">Attiva da {int(a["price"])}€/mese</a></div>'
                  '</div></div></section>')
    html = f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PHAI · Risultati e backtest in chiaro</title>
<meta name="description" content="I risultati reali di ogni strategia PHAI: grafico, win rate, drawdown — in chiaro, prima di registrarti.">
<style>
:root{{--bg:#0a0e18;--panel:#121829;--panel2:#1a2236;--border:#283149;--text:#e9ebf2;--muted:#8b94ab;--accent:#cba65c;--green:#3ddc97;--red:#f1707b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}}
a{{color:inherit}}
.pubnav{{position:sticky;top:0;z-index:50;background:rgba(10,14,24,.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}}
.pn-wrap{{max-width:1100px;margin:0 auto;display:flex;align-items:center;gap:18px;padding:11px 18px}}
.pn-brand{{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--text)}}
.pn-brand img{{width:30px;height:30px}}.pn-brand b{{font-size:16px;font-weight:800;letter-spacing:1px}}.pn-brand i{{font-style:normal;color:var(--accent);font-size:9px;letter-spacing:2px}}
.pn-links{{display:flex;gap:4px;margin-left:auto;flex-wrap:wrap}}
.pn-link{{font-size:13.5px;font-weight:600;color:var(--muted);text-decoration:none;padding:7px 11px;border-radius:8px}}
.pn-link:hover{{color:var(--text);background:#161e30}}.pn-link.on{{color:var(--accent)}}
.pn-cta{{font-size:13.5px;font-weight:700;color:#0a0e18;background:var(--accent);text-decoration:none;padding:8px 16px;border-radius:9px}}
.hero{{max-width:1100px;margin:0 auto;padding:40px 18px 10px;text-align:center}}
.hero h1{{font-size:34px;font-weight:800;line-height:1.15}}
.hero p{{color:var(--muted);font-size:15px;margin-top:12px;max-width:640px;margin-left:auto;margin-right:auto}}
.wrap{{max-width:1100px;margin:0 auto;padding:18px 18px 70px}}
.rengine{{margin-top:30px}}
.reng-h{{display:flex;align-items:center;gap:10px;margin:0 2px 14px;flex-wrap:wrap}}
.reng-h .dot{{width:12px;height:12px;border-radius:50%}}
.reng-nm{{font-size:18px;font-weight:800}}.reng-tg{{font-size:12px;color:var(--muted)}}
.rgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}}
.rcard{{background:linear-gradient(180deg,#161e30,#121829);border:1px solid var(--border);border-radius:16px;padding:18px}}
.rtop{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}}
.rname{{font-size:18px;font-weight:800}}.rtag{{font-size:12.5px;color:#aeb4c0;margin-top:3px;line-height:1.45}}
.rstat{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.4px;padding:3px 8px;border-radius:7px;white-space:nowrap}}
.rstat.live{{background:rgba(61,220,151,.16);color:var(--green)}}.rstat.soon{{background:#2a3146;color:#aeb7cc}}
.rcap{{font-size:12px;color:var(--muted);margin:12px 0 4px}}.rcap b{{color:var(--text)}}.rspan{{opacity:.8}}
.rchart{{margin:4px 0 10px}}.eqsvg{{width:100%;height:150px;display:block}}
.rsoon{{padding:34px 10px;text-align:center;color:var(--muted);font-size:13px;background:#0f1420;border:1px dashed var(--border);border-radius:10px}}
.rkpis{{display:flex;gap:16px;margin-bottom:8px}}
.rk b{{display:block;font-size:18px;font-weight:800}}.rk b.pos{{color:var(--green)}}.rk b.neg{{color:var(--red)}}
.rk span{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}}
.rsec{{margin-top:12px}}.rsec h4{{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--accent);margin-bottom:4px}}
.rsec p{{font-size:13px;line-height:1.55;color:#cfd4de}}
.rcta{{display:flex;gap:9px;flex-wrap:wrap;margin-top:16px}}
.rbtn{{flex:1;text-align:center;text-decoration:none;font-weight:700;font-size:13.5px;padding:11px 12px;border-radius:10px;white-space:nowrap}}
.rbtn.gold{{background:var(--accent);color:#0a0e18}}.rbtn.ghost{{background:transparent;border:1px solid var(--border);color:var(--text)}}
.rbtn.ghost:hover{{border-color:var(--accent);color:var(--accent)}}
.disc{{max-width:1100px;margin:10px auto 0;padding:0 18px;color:var(--muted);font-size:11.5px;text-align:center}}
@media(max-width:560px){{.hero h1{{font-size:26px}}.rgrid{{grid-template-columns:1fr}}.pn-links{{display:none}}}}
</style></head><body>
{_public_nav("risultati")}
<div class="hero">
<div style="display:inline-block;font-size:12px;font-weight:700;color:var(--accent);border:1px solid var(--border);border-radius:999px;padding:5px 14px;margin-bottom:16px">✓ Validato su 16 anni di dati reali · disdici quando vuoi</div>
<h1>Smetti di indovinare.<br>Metti al lavoro strategie testate su <span style="color:var(--accent)">16 anni</span> di mercato.</h1>
<p>Ogni strategia PHAI la vedi <b>prima</b> di pagare: grafico del capitale, win rate, drawdown — in chiaro, niente screenshot finti. La attivi sul tuo conto in automatico, oppure ricevi <b>solo i segnali via notifica push</b>. Da <b>4€/mese</b>, disdici quando vuoi.</p>
<div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:20px"><a class="rbtn gold" href="#strategie" style="padding:12px 22px;font-size:15px">Scegli la tua strategia ↓</a><a class="rbtn ghost" href="/demo" style="padding:12px 22px;font-size:15px">Provala nella Demo</a></div>
</div>
<div class="wrap" id="strategie">{"".join(blocks)}
<div class="disc">Backtest = simulazione storica su dati reali, non promessa di rendimenti futuri. Il trading comporta rischi: puoi perdere il capitale. La garanzia è sul software, mai sui profitti.</div>
</div></body></html>"""
    return HTMLResponse(html)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(open("templates/login.html").read())


@app.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    """Squeeze page HVCO (opt-in report) per il traffico freddo degli annunci."""
    return _serve_page("squeeze", request)


@app.get("/report/leggi", response_class=HTMLResponse)
async def report_read(request: Request):
    """Il report vero (lead magnet visionabile), multilingua, consegnato via {{report}} nella nurture."""
    return _serve_page("report_read", request)


# --- Mappa email (admin): mostra cosa parte a ogni trigger, letta dalla sequenza vera ---
_TRIGGER_IT = {
    "opt-in": "Qualcuno lascia l'email (squeeze/landing). Parte la sequenza che scalda il lead.",
    "no_acquisto": "Il lead ha finito la nurture ma non ha comprato: ultimi richiami.",
    "acquisto": "Il cliente ha comprato: benvenuto + licenza + come iniziare.",
    "nessun_dato_24h": "Ha comprato ma dopo 24h l'EA non manda ancora dati: email di aiuto installazione.",
    "primo_dato": "L'EA ha iniziato a mandare dati (è attivo!): email dei primi giorni d'uso.",
    "ricorrente_settimanale": "Riepilogo settimanale automatico.",
    "ricorrente_mensile": "Riepilogo mensile automatico.",
    "trade_chiuso_profit": "Dopo un trade chiuso in profitto: email di trasparenza.",
    "mese_piatto": "Un mese senza trade: email 'aspettare è parte della strategia'.",
    "starter_limite_coppie": "Usa solo la strategia base: proposta di sbloccare le altre.",
    "pro_attivo_3mesi": "Cliente Pro da 3 mesi: offerta piano annuale.",
    "heavy_user_ai": "Usa molto l'assistente AI: proposta portfolio/elite.",
    "pre_disdetta_o_carta_fallita": "Sta per disdire o carta fallita: win-back.",
    "cliente_soddisfatto": "Cliente soddisfatto: invito a portare un amico (referral).",
}
_FLOWS = [
    ("nurture", "🌱 NURTURE", "Lead freddo — ha lasciato l'email (dalla squeeze/annuncio)", "#3fcf8e"),
    ("postseq", "🔁 RICHIAMO", "Non ha comprato dopo la nurture", "#cba65c"),
    ("onboarding", "📦 ONBOARDING", "Ha comprato — attivazione e primi giorni", "#6ea8fe"),
    ("retention", "💛 RETENTION", "Cliente attivo — fidelizza, upsell, referral", "#f1707b"),
]
_LINK_LABELS = {
    "{{demo}}": "[link: Demo]", "{{sblocca}}": "[link: Checkout]", "{{report}}": "[link: Report]",
    "{{guida}}": "[link: Guida]", "{{app}}": "[link: App]", "{{referral}}": "[link: Referral]",
    "{{dfy}}": "[link: DFY]", "{{unsubscribe}}": "[link: Disiscrizione]",
    "{{license_key}}": "[la sua license key]", "[Nome]": "[Nome cliente]",
}


def _email_preview_html(body: str) -> str:
    import html as _html
    try:
        from email_drip import _price_map
        for tok, val in _price_map().items():
            body = body.replace(tok, val)
    except Exception:
        pass
    for tok, lab in _LINK_LABELS.items():
        body = body.replace(tok, lab)
    return _html.escape(body).replace("\n", "<br>")


@app.get("/admin/emails", response_class=HTMLResponse)
async def admin_emails(user: User = Depends(auth.current_user)):
    """Mappa leggibile delle pipeline email: cosa parte a ogni trigger (solo owner)."""
    import html as _html
    oid = _owner_id()
    if oid is not None and user.id != oid:
        return HTMLResponse("<h1 style='font-family:sans-serif'>Non autorizzato</h1>", status_code=403)
    try:
        with open("email_campaign.json", encoding="utf-8") as f:
            camp = json.load(f)
    except Exception as e:
        return HTMLResponse(f"<pre>Errore lettura sequenza: {_html.escape(str(e))}</pre>", status_code=500)

    # legenda trigger (solo quelli davvero usati, in ordine di prima comparsa)
    seen, leg_rows = set(), []
    for e in camp:
        tr = e.get("trigger", "?")
        if tr not in seen:
            seen.add(tr)
            leg_rows.append(f"<tr><td class='tg'>{_html.escape(tr)}</td><td>{_html.escape(_TRIGGER_IT.get(tr, '—'))}</td></tr>")
    legend = "<table class='leg'>" + "".join(leg_rows) + "</table>"

    flows_html = []
    for seq, title, sub, col in _FLOWS:
        rows = [e for e in camp if e.get("sequence") == seq]
        rows.sort(key=lambda e: (e.get("delay_days", 0), e.get("step", 0)))
        if not rows:
            continue
        cards = []
        for e in rows:
            dd = e.get("delay_days", 0)
            when = "subito" if dd == 0 else f"+{dd} giorn{'o' if dd == 1 else 'i'}"
            cards.append(
                "<div class='card'>"
                f"<div class='chead'><span class='when'>⏱ {when}</span>"
                f"<span class='trig'>{_html.escape(e.get('trigger','?'))}</span></div>"
                f"<div class='subj'>{_html.escape(e.get('subject',''))}</div>"
                f"<details><summary>vedi email</summary>"
                f"<div class='prev'>Anteprima: {_html.escape(e.get('preview',''))}</div>"
                f"<div class='body'>{_email_preview_html(e.get('body',''))}</div></details>"
                "</div>"
            )
        flows_html.append(
            f"<section class='flow'><div class='fhead' style='border-color:{col}'>"
            f"<h2 style='color:{col}'>{_html.escape(title)}</h2>"
            f"<span class='fsub'>{_html.escape(sub)} · {len(rows)} email</span></div>"
            + "".join(cards) + "</section>"
        )

    page = f"""<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PHAI — Mappa email</title><style>
:root{{--bg:#0a0e18;--panel:#121829;--panel2:#0e1422;--border:#283149;--text:#e9ebf2;--muted:#8b94ab;--accent:#cba65c}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.55;padding:26px 16px}}
.wrap{{max-width:920px;margin:0 auto}}
h1{{font-size:26px;margin-bottom:6px}} .intro{{color:var(--muted);margin-bottom:22px;font-size:15px}}
.leg{{width:100%;border-collapse:collapse;margin-bottom:30px;font-size:13.5px;background:var(--panel);border-radius:12px;overflow:hidden}}
.leg td{{padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:top}}
.leg tr:last-child td{{border-bottom:none}} .leg .tg{{color:var(--accent);font-weight:700;white-space:nowrap;font-family:ui-monospace,monospace}}
.flow{{margin-bottom:26px}}
.fhead{{border-left:4px solid;padding:4px 0 4px 12px;margin-bottom:12px}}
.fhead h2{{font-size:18px}} .fsub{{color:var(--muted);font-size:13px}}
.card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:13px 15px;margin-bottom:9px}}
.chead{{display:flex;gap:10px;align-items:center;margin-bottom:5px;flex-wrap:wrap}}
.when{{font-size:12px;color:var(--muted);font-weight:600}}
.trig{{font-size:11px;font-family:ui-monospace,monospace;color:var(--accent);background:rgba(203,166,92,.1);border:1px solid rgba(203,166,92,.3);padding:1px 8px;border-radius:999px}}
.subj{{font-weight:600;font-size:15px}}
details{{margin-top:8px}} summary{{cursor:pointer;color:var(--accent);font-size:13px}}
.prev{{color:var(--muted);font-size:13px;font-style:italic;margin:8px 0 6px}}
.body{{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:12px 14px;font-size:13.5px;color:#c7cde0;white-space:normal}}
</style></head><body><div class="wrap">
<h1>📬 Mappa email — cosa parte a ogni trigger</h1>
<p class="intro">Generata dalla sequenza reale (<code>email_campaign.json</code>): è sempre allineata a ciò che il sistema invia davvero. Prezzi già risolti dal listino; i link sono mostrati come etichette.</p>
<h3 style="margin-bottom:8px">Legenda trigger</h3>{legend}
{''.join(flows_html)}
</div></body></html>"""
    return HTMLResponse(page)


@app.get("/unsub", response_class=HTMLResponse)
async def unsub(e: str = ""):
    """Disiscrizione email marketing. Segna l'indirizzo come unsubscribed (crea il
    record lead se non esiste, così vale anche per i clienti). Usata dal footer email."""
    em = (e or "").strip().lower()
    if em and "@" in em:
        async with AsyncSession() as session:
            row = (await session.execute(select(Lead).where(Lead.email == em))).scalar_one_or_none()
            if row:
                row.unsubscribed = True
            else:
                session.add(Lead(email=em, source="unsub", unsubscribed=True))
            await session.commit()
    return HTMLResponse(
        "<div style='font-family:system-ui;background:#0a0e18;color:#e9ebf2;min-height:100vh;"
        "display:flex;align-items:center;justify-content:center;text-align:center;padding:24px'>"
        "<div><h2 style='color:#cba65c'>Disiscrizione completata</h2>"
        "<p>Non riceverai più email di marketing da PHAI. Mi dispiace vederti andare.</p></div></div>"
    )


@app.get("/demo")
async def demo(request: Request):
    """Demo read-only: auto-login come utente demo (dati di esempio). Niente
    registrazione, niente carta. Protegge la quota AI col rate-limit per-utente."""
    async with AsyncSession() as session:
        u = (await session.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
    if not u:
        return RedirectResponse("/login", status_code=302)
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(
        auth.COOKIE_NAME, auth.create_session_token(u.id),
        httponly=True, max_age=auth.SESSION_MAX_AGE, samesite="lax", secure=auth.COOKIE_SECURE,
    )
    return resp


@app.post("/api/lead")
async def api_lead(request: Request):
    """Cattura email dalla landing/HVCO (lead di marketing)."""
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if "@" not in email or "." not in email:
        return JSONResponse({"error": "Email non valida"}, status_code=400)
    async with AsyncSession() as session:
        session.add(Lead(email=email, source=(body.get("source") or "landing")[:40], lang=(body.get("lang") or "")[:8] or None))
        try:
            await session.commit()
        except Exception:
            await session.rollback()
    return {"ok": True}


# --- PWA: manifest e service worker (pubblici, a scope root) ---
@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse("static/manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon-32.png", media_type="image/png")


@app.post("/api/ea/validate")
async def ea_validate(request: Request):
    """L'EA valida la licenza all'avvio e periodicamente. Lega la key al conto
    (primo uso) e ritorna stato + kill-switch/rischio dalla config centrale."""
    body = await request.json()
    account = str(body.get("account") or "").strip()
    broker = (body.get("broker") or "")[:80]
    symbol = (body.get("symbol") or "").upper()
    lk, err = await _resolve_license(body.get("key"))
    if err:
        return PlainTextResponse(_kv({"ok": 0, "reason": err}))
    if not account:
        return PlainTextResponse(_kv({"ok": 0, "reason": "no_account"}))
    async with AsyncSession() as session:
        lk = await session.get(LicenseKey, lk.id)
        if lk.bound_account and lk.bound_account != account:
            return PlainTextResponse(_kv({"ok": 0, "reason": "bound_other_account"}))
        if not lk.bound_account:
            lk.bound_account = account
            lk.bound_broker = broker
        lk.last_seen = datetime.utcnow()
        plan = lk.plan or "pro"
        await session.commit()
    # Gate EA: solo i piani con EA (pro/elite) possono far girare l'Expert Advisor.
    # Starter = solo segnali: licenza valida ma l'EA non opera.
    if not entitlements.can_ea(plan):
        return PlainTextResponse(_kv({"ok": 0, "plan": plan, "reason": "plan_no_ea"}))
    # Gate per-EA: l'utente fa girare l'EA solo sui simboli che possiede (single/pack/portfolio).
    if symbol and not entitlements.can_ea_symbol(plan, symbol):
        return PlainTextResponse(_kv({"ok": 0, "plan": plan, "reason": "ea_not_owned"}))
    cfg = _load_ea_config()
    dft = cfg.get("default", {})
    sym_cfg = (cfg.get("symbols") or {}).get(symbol) or dft
    enabled = 1 if sym_cfg.get("enabled", True) else 0
    risk = sym_cfg.get("risk", dft.get("risk", 10))
    return PlainTextResponse(_kv({"ok": 1, "plan": plan, "enabled": enabled, "risk": risk, "reason": ""}))


@app.post("/api/ea/ingest")
async def ea_ingest(request: Request):
    """Telemetria multi-tenant: l'EA invia gli eventi (open/close/skip/account/
    market); vengono salvati taggati con l'utente della licenza."""
    body = await request.json()
    lk, err = await _resolve_license(body.get("key"))
    if err:
        return PlainTextResponse(_kv({"ok": 0, "reason": err}))
    uid = lk.used_by_user_id
    if uid is None:
        # La key non è ancora collegata a un account app: NON misfilare i dati
        # (andrebbero al proprietario). Il cliente deve prima registrare l'app.
        return PlainTextResponse(_kv({"ok": 0, "reason": "register_app_first"}))
    events = body.get("events")
    if events is None:
        ev = {k: v for k, v in body.items() if k != "key"}
        events = [ev] if ev.get("action") else []
    count = 0
    for ev in events:
        t = ev.get("t")
        if isinstance(t, (int, float)):
            try:
                ev["t"] = datetime.fromtimestamp(t)
            except Exception:
                ev["t"] = datetime.utcnow()
        elif t is None:
            ev["t"] = datetime.utcnow()
        try:
            await process_event(ev, uid)
            count += 1
        except Exception:
            log.exception("ingest evento fallito")
    return PlainTextResponse(_kv({"ok": 1, "count": count}))


@app.get("/api/ea/config")
async def ea_config(key: str = "", symbol: str = ""):
    """Configurazione strategia centralizzata per simbolo (kill-switch, rischio,
    pattern attivi in formato compatto entry:dir:exit:sl:slpips:tp:trail)."""
    lk, err = await _resolve_license(key)
    if err:
        return PlainTextResponse(_kv({"ok": 0, "reason": err}))
    cfg = _load_ea_config()
    dft = cfg.get("default", {})
    sym_cfg = (cfg.get("symbols") or {}).get(symbol.upper()) or dft
    enabled = 1 if sym_cfg.get("enabled", True) else 0
    risk = sym_cfg.get("risk", dft.get("risk", 10))
    pats = sym_cfg.get("patterns") or []
    patline = ",".join(
        f"{p.get('entry',0)}:{p.get('dir',0)}:{p.get('exit',0)}:{p.get('sl',0)}:"
        f"{p.get('slpips',0)}:{p.get('tp',0)}:{p.get('trail',0)}"
        for p in pats
    )
    return PlainTextResponse(_kv({"ok": 1, "enabled": enabled, "risk": risk, "npat": len(pats), "patterns": patline}))


EA_FILES_DIR = os.path.join(os.path.dirname(__file__), "ea_files")


@app.get("/api/ea/downloads")
async def ea_downloads(user: User = Depends(auth.current_user)):
    """Per la pagina download del cliente: la sua license key + gli EA che il piano sblocca."""
    plan = await _user_plan(user)
    owned = entitlements.owned_eas(plan)
    async with AsyncSession() as session:
        lk = (await session.execute(
            select(LicenseKey).where(
                LicenseKey.used_by_user_id == user.id,
                LicenseKey.active.is_(True), LicenseKey.revoked.is_(False)
            ).order_by(desc(LicenseKey.id)).limit(1)
        )).scalar_one_or_none()
    key = lk.key if lk else ""
    eas = []
    for e in catalog.EAS:
        is_owned = e["id"] in owned
        has_file = os.path.isfile(os.path.join(EA_FILES_DIR, f"{e['id']}.ex5"))
        eas.append({
            "id": e["id"], "symbol": e["symbol"], "name": e["name"], "engine": e["engine"],
            "owned": is_owned, "url": (f"/api/ea/file/{e['id']}" if (is_owned and has_file) else None),
        })
    indic = "/api/ea/file/PHAI_Median" if os.path.isfile(os.path.join(EA_FILES_DIR, "PHAI_Median.ex5")) else None
    return {"key": key, "eas": eas, "indicator_url": indic}


@app.get("/api/ea/file/{ea_id}")
async def ea_file(ea_id: str, user: User = Depends(auth.current_user)):
    """Scarica il .ex5 di un EA, SOLO se il piano del cliente lo possiede. PHAI_Median e' libero
    (serve agli EA Base). Path-safe."""
    ea_id = os.path.basename(ea_id)
    path = os.path.join(EA_FILES_DIR, f"{ea_id}.ex5")
    if not os.path.isfile(path):
        return JSONResponse({"error": "file non disponibile"}, status_code=404)
    if ea_id != "PHAI_Median":
        plan = await _user_plan(user)
        if ea_id not in entitlements.owned_eas(plan):
            return JSONResponse({"error": "non incluso nel tuo piano"}, status_code=403)
    dl_name = f"{ea_id}.ex5" if ea_id.startswith("PHAI_") else f"PHAI_{ea_id}.ex5"
    return FileResponse(path, filename=dl_name, media_type="application/octet-stream")


@app.get("/api/ea/set/{ea_id}")
async def ea_set(ea_id: str, user: User = Depends(auth.current_user)):
    """Genera un preset MT5 (.set) con la license key del cliente GIA' compilata, così
    caricandolo gli input (key compresa) si riempiono da soli. Solo per EA posseduti."""
    ea_id = os.path.basename(ea_id)
    if ea_id not in entitlements.owned_eas(await _user_plan(user)):
        return JSONResponse({"error": "non incluso nel tuo piano"}, status_code=403)
    async with AsyncSession() as session:
        lk = (await session.execute(
            select(LicenseKey).where(
                LicenseKey.used_by_user_id == user.id,
                LicenseKey.active.is_(True), LicenseKey.revoked.is_(False)
            ).order_by(desc(LicenseKey.id)).limit(1)
        )).scalar_one_or_none()
    key = lk.key if lk else ""
    # .set MT5: una riga input=valore. Solo i 3 input PHAI; il resto resta ai default validati.
    content = ("InpUseServer=true\r\n"
               "InpServerUrl=https://app.phai.io\r\n"
               f"InpLicenseKey={key}\r\n")
    return PlainTextResponse(content, headers={
        "Content-Disposition": f'attachment; filename="PHAI_{ea_id}.set"'})


_EA_TF = {"EURUSD": "D1 (giornaliero)", "GBPUSD": "D1 (giornaliero)", "USDCHF": "D1 (giornaliero)",
          "EURGBP": "H6 (6 ore)", "GBPCHF": "D1 (giornaliero)"}


@app.get("/api/ea/guide/{ea_id}", response_class=HTMLResponse)
async def ea_guide(ea_id: str, user: User = Depends(auth.current_user)):
    """Guida di installazione PERSONALIZZATA per un EA (simbolo, timeframe, indicatore se Base,
    license key gia' dentro). Pagina HTML stampabile/salvabile. Solo per EA posseduti."""
    ea_id = os.path.basename(ea_id)
    e = catalog.EA_BY_ID.get(ea_id)
    if not e or ea_id not in entitlements.owned_eas(await _user_plan(user)):
        return HTMLResponse("<h3 style='font-family:sans-serif'>Guida non disponibile per questo EA o piano.</h3>", status_code=403)
    async with AsyncSession() as session:
        lk = (await session.execute(
            select(LicenseKey).where(
                LicenseKey.used_by_user_id == user.id,
                LicenseKey.active.is_(True), LicenseKey.revoked.is_(False)
            ).order_by(desc(LicenseKey.id)).limit(1)
        )).scalar_one_or_none()
    key = lk.key if lk else "(la trovi nel tuo account PHAI)"
    sym = e["symbol"]; tf = _EA_TF.get(ea_id, "D1"); is_base = (e["engine"] == "base")
    name = e["name"] if isinstance(e["name"], str) else e["name"].get("it", ea_id)
    dl_ind = "<li>l'<b>indicatore PHAI_Median.ex5</b></li>" if is_base else ""
    step_ind = "<li>Copia <b>PHAI_Median.ex5</b> in <code>MQL5\\Indicators</code></li>" if is_base else ""
    note_ind = (" e l'<b>indicatore</b> in <code>Indicators</code>") if is_base else ""
    err_ind = ("<li><b>(Base) Nessun segnale / errore indicatore</b> → PHAI_Median non è in "
               "<code>MQL5\\Indicators</code> o non è compilato.</li>") if is_base else ""
    html = f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PHAI · Guida installazione {name}</title>
<style>
body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:780px;margin:0 auto;padding:28px 20px;color:#1a2030;line-height:1.6}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:26px 0 8px;color:#0a5}}
.sub{{color:#667;margin-bottom:18px}}
.box{{background:#f4f6fb;border:1px solid #dde3ef;border-radius:10px;padding:14px 16px;margin:14px 0}}
.key{{font-family:ui-monospace,monospace;background:#0a0e18;color:#cba65c;padding:8px 12px;border-radius:7px;display:inline-block;word-break:break-all}}
ol{{padding-left:22px}} li{{margin:7px 0}} code{{background:#eceff6;padding:1px 6px;border-radius:5px;font-size:13px}}
.warn{{background:#fff5f5;border-color:#f3c0c0}} .ok{{background:#f0fbf4;border-color:#bfe6cf}}
@media print{{.noprint{{display:none}}}}
button{{padding:9px 16px;border:0;border-radius:8px;background:#cba65c;color:#0a0e18;font-weight:700;cursor:pointer}}
</style></head><body>
<h1>Guida installazione — {name}</h1>
<div class="sub">Simbolo <b>{sym}</b> · Timeframe <b>{tf}</b> · MetaTrader 5</div>
<div class="box"><b>La tua license key</b><br><span class="key">{key}</span><br>
<small>È già inclusa nel file <b>.set</b> che scarichi: caricandolo non devi digitarla.</small></div>

<h2>1) Scarica dall'app</h2>
<ul><li>il file <b>EA (.ex5)</b></li><li>il <b>preset (.set)</b> (con la tua key dentro)</li>{dl_ind}</ul>

<h2>2) Copia i file in MetaTrader 5</h2>
<ol>
<li>In MT5: <b>File → Apri cartella dati</b> (la cartella DATI), poi entra in <code>MQL5</code>.</li>
<li>Copia l'<b>EA .ex5</b> in <code>MQL5\\Experts</code>{note_ind}.</li>
{step_ind}
<li>In MT5, <b>Navigatore → tasto destro su "Expert Advisors" → Aggiorna</b>.</li>
</ol>

<h2>3) Autorizza il server (una volta sola)</h2>
<ol><li><b>Strumenti → Opzioni → scheda "Expert Advisors"</b>.</li>
<li>Spunta <b>"Consenti WebRequest per gli URL elencati"</b> e aggiungi: <code>https://app.phai.io</code></li></ol>

<h2>4) Avvia l'EA</h2>
<ol>
<li>Apri il grafico <b>{sym}</b>, timeframe <b>{tf}</b>.</li>
<li>Trascina l'EA dal Navigatore sul grafico.</li>
<li>Scheda <b>Input</b> → in basso <b>"Carica"</b> → scegli il <b>.set</b> (key compilata da sola).</li>
<li>Spunta <b>"Consenti trading algoritmico"</b> → <b>OK</b>.</li>
<li>In alto, attiva il pulsante <b>"Trading algoritmico"</b> (verde).</li>
</ol>

<div class="box ok"><b>5) Verifica che funzioni</b><br>
In basso, scheda <b>"Esperti"</b>: devi vedere <b>"INIT OK"</b> e <b>"PHAI: licenza OK"</b>.
Sul grafico in alto a destra una <b>faccina sorridente</b> = EA attivo.</div>

<h2>Problemi frequenti</h2>
<ul>
<li><b>"WebRequest fallita / Autorizza…"</b> → manca l'URL al punto 3. Aggiungi <code>https://app.phai.io</code> e riattacca l'EA.</li>
<li><b>"LICENZA NON VALIDA"</b> → key sbagliata/scaduta, o {sym} non è nel tuo piano.</li>
<li><b>Faccina triste / non opera</b> → attiva "Trading algoritmico" (punto 4).</li>
{err_ind}
</ul>
<div class="box noprint" style="text-align:center"><button onclick="window.print()">🖨️ Stampa / salva in PDF</button></div>
<div class="sub" style="margin-top:20px">Il PC (o un VPS) deve restare acceso con MT5 aperto perché l'EA operi. Dubbi? Chiedi all'assistente PHAI in chat.</div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/api/catalog")
async def api_catalog(lang: str = "it", user: User = Depends(auth.current_user)):
    """Catalogo per lo showroom 'Strategie': i due motori, i singoli EA (con stato
    attivo/bloccato per QUESTO utente), i pacchetti e il portfolio con i prezzi.
    Le statistiche e il grafico di ogni EA arrivano da /api/backtest/overview?symbol=."""
    plan = await _user_plan(user)
    owned = entitlements.owned_eas(plan)
    L = lambda d: catalog.tr(d, lang)
    eas = []
    for e in catalog.EAS:
        is_owned = e["id"] in owned
        item = {
            "id": e["id"], "engine": e["engine"], "symbol": e["symbol"], "live": e["live"],
            "flagship": e.get("flagship", False),
            "name": e["name"], "tagline": L(e["tagline"]), "mechanism": L(e["mechanism"]),
            "risk": L(e["risk"]), "owned": is_owned,
            "engine_name": L(catalog.ENGINES[e["engine"]]["name"]),
            "engine_color": catalog.ENGINES[e["engine"]]["color"],
        }
        if not is_owned:
            item["offer"] = catalog.offer_for_ea(e["id"])
        eas.append(item)
    engines = {k: {"key": k, "name": L(v["name"]), "tagline": L(v["tagline"]), "color": v["color"]}
               for k, v in catalog.ENGINES.items()}
    packs = [{"id": p["id"], "name": L(p["name"]), "tagline": L(p["tagline"]),
              "eas": p["eas"], "price": p["price"], "stats": p.get("stats"),
              "recommended": p.get("recommended", False),
              "owned": set(p["eas"]).issubset(owned)}
             for p in catalog.PACKS]
    portfolio = {"id": "portfolio", "name": L(catalog.PORTFOLIO["name"]), "tagline": L(catalog.PORTFOLIO["tagline"]),
                 "eas": catalog.PORTFOLIO["eas"], "price": catalog.PORTFOLIO["price"],
                 "owned": set(catalog.ALL_EA_IDS).issubset(owned)}
    assistant = {"id": catalog.ASSISTANT["id"], "name": L(catalog.ASSISTANT["name"]),
                 "tagline": L(catalog.ASSISTANT["tagline"]), "features": L(catalog.ASSISTANT["features"]),
                 "price": catalog.ASSISTANT["price"], "owned": entitlements.can_signals(plan)}
    return {
        "engines": engines, "eas": eas, "packs": packs, "portfolio": portfolio,
        "assistant": assistant,
        "single_price": catalog.SINGLE_PRICE, "signals_price": catalog.SIGNALS_PRICE,
        "owned": sorted(owned), "plan": plan or "",
    }


@app.get("/api/backtest/export")
async def backtest_export(symbol: str = "", user: User = Depends(auth.current_user)):
    """Scarica i risultati del backtest come CSV (dal database, quindi sempre coerente
    con ciò che è mostrato). symbol vuoto = tutti i simboli. 404 con avviso se non ci
    sono dati per quel simbolo."""
    import csv
    import io
    async with AsyncSession() as session:
        q = _bt_scope(select(BacktestTrade), symbol).where(BacktestTrade.exit_time.isnot(None))
        rows = (await session.execute(q.order_by(BacktestTrade.exit_time))).scalars().all()
    if not rows:
        return JSONResponse({"ok": False, "reason": "no_data", "symbol": (symbol or "tutti")}, status_code=404)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["symbol", "pattern", "dir", "entry_time", "entry_price", "exit_time",
                "exit_price", "lot", "pnl_pt", "pnl_money", "reason", "duration_d"])
    for r in rows:
        w.writerow([r.symbol, r.pattern, r.dir, r.entry_time, r.entry_price, r.exit_time,
                    r.exit_price, r.lot, r.pnl_pt, r.pnl_money, r.reason, r.duration_d])
    fname = f"phai_backtest_{(symbol or 'tutti').upper()}.csv"
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ---------------------------------------------------------------------------
# Pagamenti → emissione license key. Motore agnostico (licensing.py):
#   - PayPal (carte + PayPal) via webhook automatico
#   - bonifici / vendite manuali via endpoint admin (emetti con un click)
# ---------------------------------------------------------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
PAYPAL_API = os.getenv("PAYPAL_API", "https://api-m.paypal.com")  # sandbox: api-m.sandbox.paypal.com


@app.post("/api/admin/issue-license")
async def admin_issue_license(request: Request):
    """Emette una license key manualmente (bonifico, vendita diretta, omaggio).
    Protetto da header X-Admin-Token == env ADMIN_TOKEN."""
    if not ADMIN_TOKEN or request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return JSONResponse({"error": "non autorizzato"}, status_code=401)
    body = await request.json()
    res = await licensing.issue_license(
        (body.get("email") or "").strip().lower() or None,
        plan=body.get("plan") or "pro",
        source=body.get("source") or "manual",
        external_id=body.get("external_id") or None,
        months=body.get("months"),
    )
    return {"ok": True, **res}


async def _paypal_token(client):
    r = await client.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        auth=(os.getenv("PAYPAL_CLIENT_ID", ""), os.getenv("PAYPAL_SECRET", "")),
        data={"grant_type": "client_credentials"},
    )
    return r.json().get("access_token")


async def _paypal_verify(headers, event, client, token) -> bool:
    wid = os.getenv("PAYPAL_WEBHOOK_ID")
    if not wid or not token:
        return False
    payload = {
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "cert_url": headers.get("paypal-cert-url"),
        "auth_algo": headers.get("paypal-auth-algo"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "webhook_id": wid,
        "webhook_event": event,
    }
    r = await client.post(
        f"{PAYPAL_API}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    return r.json().get("verification_status") == "SUCCESS"


@app.post("/api/pay/paypal/webhook")
async def paypal_webhook(request: Request):
    """Webhook PayPal: alla conferma del pagamento/abbonamento emette la key;
    alla cancellazione disattiva la licenza (l'EA smette di aprire)."""
    if not (os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_SECRET") and os.getenv("PAYPAL_WEBHOOK_ID")):
        return JSONResponse({"error": "paypal non configurato"}, status_code=503)
    raw = await request.body()
    try:
        event = json.loads(raw)
    except Exception:
        return JSONResponse({"error": "payload non valido"}, status_code=400)
    async with httpx.AsyncClient(timeout=15) as client:
        token = await _paypal_token(client)
        if not await _paypal_verify(request.headers, event, client, token):
            log.warning("PayPal webhook: firma NON valida — ignorato")
            return JSONResponse({"error": "firma non valida"}, status_code=400)

    etype = event.get("event_type", "")
    res = event.get("resource", {}) or {}
    log.info("PayPal webhook verificato: %s", etype)
    try:
        plan_map = json.loads(os.getenv("PAYPAL_PLAN_MAP", "{}"))
    except Exception:
        plan_map = {}

    ISSUE = ("BILLING.SUBSCRIPTION.ACTIVATED", "PAYMENT.SALE.COMPLETED",
             "CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED")
    OFF = ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.SUSPENDED",
           "BILLING.SUBSCRIPTION.EXPIRED")
    if etype in ISSUE:
        email = ((res.get("subscriber") or {}).get("email_address")
                 or (res.get("payer") or {}).get("email_address")
                 or res.get("custom_id"))
        plan = plan_map.get(res.get("plan_id")) or "pro"
        await licensing.issue_license(email, plan=plan, source="paypal", external_id=res.get("id"))
    elif etype in OFF:
        await licensing.set_active_by_external(res.get("id"), False)
    elif etype == "BILLING.SUBSCRIPTION.UPDATED":
        await licensing.set_active_by_external(res.get("id"), True)
    return {"ok": True}


@app.get("/api/pay/config")
async def pay_config():
    """Config pubblica per i pulsanti PayPal sul checkout (client-id + plan id)."""
    cid = os.getenv("PAYPAL_CLIENT_ID", "")
    return {
        "configured": bool(cid and os.getenv("PAYPAL_SECRET")),
        "client_id": cid,
        "currency": os.getenv("PAYPAL_CURRENCY", "EUR"),
        "plans": {
            "starter": {"plan_id": os.getenv("PAYPAL_PLAN_STARTER", ""), "label": "Starter — 49€/mese", "kind": "subscription"},
            "pro": {"plan_id": os.getenv("PAYPAL_PLAN_PRO", ""), "label": "Pro — 97€/mese", "kind": "subscription"},
            "lifetime": {"price": os.getenv("PAYPAL_LIFETIME_PRICE", "997"), "label": "Lifetime — pagamento unico", "kind": "order"},
        },
    }


@app.get("/api/pay/sku")
async def pay_sku(sku: str = "pro", lang: str = "it"):
    """Prezzo + etichetta di uno SKU (singolo EA / pacchetto / portfolio / signals)
    per il checkout, con l'eventuale plan_id PayPal preso dall'ambiente
    (env PAYPAL_PLAN_<SKU>, p.es. PAYPAL_PLAN_SINGLE_EURUSD / PAYPAL_PLAN_PACK_BASE)."""
    label, price = catalog.sku_label_price(sku, lang)
    env_key = "PAYPAL_PLAN_" + (sku or "").upper().replace(":", "_").replace("-", "_")
    kind = "order" if (sku or "").strip().lower() == "dfy" else "subscription"   # DFY = una tantum
    return {
        "sku": sku, "label": label, "price": price, "kind": kind,
        "plan_id": os.getenv(env_key, ""),
        "client_id": os.getenv("PAYPAL_CLIENT_ID", ""),
        "currency": os.getenv("PAYPAL_CURRENCY", "EUR"),
        "configured": bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_SECRET")),
    }


def _plan_from_paypal(plan_id: str | None):
    if plan_id and plan_id == os.getenv("PAYPAL_PLAN_STARTER"):
        return "starter"
    if plan_id and plan_id == os.getenv("PAYPAL_PLAN_PRO"):
        return "pro"
    return None


@app.post("/api/pay/paypal/confirm")
async def paypal_confirm(request: Request):
    """Chiamato dal browser dopo l'approvazione PayPal: verifica il pagamento lato
    server (abbonamento o ordine) ed emette la license key (idempotente). Il webhook
    resta come backstop affidabile."""
    if not (os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_SECRET")):
        return JSONResponse({"ok": False, "reason": "paypal non configurato"}, status_code=503)
    body = await request.json()
    email = (body.get("email") or "").strip().lower() or None
    plan_req = (body.get("plan") or "").lower()
    sub_id = body.get("subscription_id")
    order_id = body.get("order_id")
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _paypal_token(client)
        if not token:
            return JSONResponse({"ok": False, "reason": "auth"}, status_code=502)
        hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if sub_id:
            r = await client.get(f"{PAYPAL_API}/v1/billing/subscriptions/{sub_id}", headers=hdr)
            data = r.json()
            if data.get("status") not in ("ACTIVE", "APPROVED"):
                return {"ok": False, "reason": "subscription_not_active"}
            plan = _plan_from_paypal(data.get("plan_id")) or (plan_req if catalog.is_valid_sku(plan_req) else "pro")
            email = email or (data.get("subscriber") or {}).get("email_address")
            res = await licensing.issue_license(email, plan=plan, source="paypal", external_id=sub_id)
            return {"ok": True, "key": res["key"]}
        if order_id:
            r = await client.post(f"{PAYPAL_API}/v2/checkout/orders/{order_id}/capture", headers=hdr)
            data = r.json()
            if data.get("status") != "COMPLETED":
                # forse già catturato: ricontrolla
                g = await client.get(f"{PAYPAL_API}/v2/checkout/orders/{order_id}", headers=hdr)
                if g.json().get("status") != "COMPLETED":
                    return {"ok": False, "reason": "order_not_completed"}
            if not email:
                try:
                    email = data["payer"]["email_address"]
                except Exception:
                    email = None
            # Ordine una-tantum: usa lo SKU richiesto se valido, altrimenti Pro.
            plan = plan_req if catalog.is_valid_sku(plan_req) else "pro"
            res = await licensing.issue_license(email, plan=plan, source="paypal", external_id=order_id)
            return {"ok": True, "key": res["key"]}
    return JSONResponse({"ok": False, "reason": "no_id"}, status_code=400)


@app.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request):
    return _serve_page("checkout", request)


@app.get("/sitemap", response_class=HTMLResponse)
async def sitemap_page(request: Request):
    """Mappa del sito OWNER-ONLY: hub con tutte le pagine (marketing in 4 lingue,
    checkout per ogni SKU, app, dati/download) + elenco tecnico di tutte le rotte."""
    try:
        user = await auth.current_user(request)
    except Exception:
        return RedirectResponse("/login", status_code=302)
    oid = _owner_id()
    if oid is not None and user.id != oid:
        return RedirectResponse("/", status_code=302)

    LANGS = ["it", "en", "fr", "es"]
    FLAG = {"it": "🇮🇹", "en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸"}

    def card(href, title, desc, *, ext=False, langs=False):
        tgt = ' target="_blank" rel="noopener"' if ext else ""
        if langs:
            chips = " ".join(
                f'<a class="lang" href="{href}?lang={l}" target="_blank" rel="noopener">{FLAG[l]} {l.upper()}</a>'
                for l in LANGS
            )
            return (f'<div class="sm-card"><div class="sm-t">{title}</div>'
                    f'<div class="sm-d">{desc}</div><div class="sm-langs">{chips}</div></div>')
        return (f'<a class="sm-card link" href="{href}"{tgt}><div class="sm-t">{title} ↗</div>'
                f'<div class="sm-d">{desc}</div></a>')

    # --- Sezioni ---
    marketing = [
        card("/landing", "Landing / Sales", "Porta d'ingresso completa (hero → prova → prezzi → FAQ → cosa fa / cosa NON fa). Sempre visibile, anche da loggato.", langs=True),
        card("/report", "Squeeze report", "Pagina a obiettivo unico: email in cambio del report.", langs=True),
        card("/demo", "Demo dal vivo", "Dashboard read-only con dati reali (auto-login demo).", ext=True),
        card("/login", "Login", "Accesso clienti.", ext=True),
        card("/login?mode=register", "Registrazione", "Creazione account con license key.", ext=True),
        card("/unsub?e=esempio@mail.com", "Disiscrizione email", "Pagina /unsub per togliersi dalle email.", ext=True),
    ]

    app_pages = [
        card("/#overview", "App · Panoramica", "Conto, attività e track record.", ext=True),
        card("/#strategie", "App · Strategie (marketplace)", "Gli EA per motore: grafico, spiegazione, sblocco.", ext=True),
        card("/#signals", "App · Segnali", "Feed segnali in tempo reale.", ext=True),
        card("/#mercato", "App · Mercato", "Stato del mercato (feature).", ext=True),
        card("/#assistant", "App · Assistente", "Chatbot AI.", ext=True),
    ]

    # Checkout per ogni SKU (dal catalogo)
    sku_list = [("signals", "PHAI Signals", catalog.SIGNALS_PRICE)]
    for e in catalog.EAS:
        sku_list.append((f"single:{e['id']}", f"Solo {e['name']}", catalog.SINGLE_PRICE))
    for p in catalog.PACKS:
        sku_list.append((p["id"], catalog.tr(p["name"]), p["price"]))
    sku_list.append(("portfolio", catalog.tr(catalog.PORTFOLIO["name"]), catalog.PORTFOLIO["price"]))
    checkout_cards = [
        card(f"/checkout?sku={sku}", f"{label} — {int(price)}€/mese", f"Checkout SKU <code>{sku}</code>.", ext=True)
        for sku, label, price in sku_list
    ]

    # Dati & download
    data_cards = [card("/api/backtest/export", "⤓ Tutti i backtest (CSV)", "Esporta tutti i trade dal database.", ext=True)]
    for e in catalog.EAS:
        if e["live"]:
            data_cards.append(card(f"/api/backtest/export?symbol={e['symbol']}",
                                   f"⤓ Backtest {e['name']} (CSV)", f"Trade di {e['symbol']} dal DB.", ext=True))
    data_cards.append(card("/api/public/track-record", "Track record pubblico (JSON)", "KPI sintetici per la landing.", ext=True))
    data_cards.append(card("/api/catalog", "Catalogo (JSON)", "Motori, EA, pacchetti, prezzi e cosa possiedi.", ext=True))

    # Tutte le rotte tecniche (auto)
    seen, rows = set(), []
    for r in app.routes:
        path = getattr(r, "path", "")
        methods = getattr(r, "methods", None)
        if not path or path.startswith("/static") or path in seen:
            continue
        seen.add(path)
        ms = ",".join(sorted(m for m in (methods or []) if m not in ("HEAD", "OPTIONS"))) or "WS"
        rows.append(f'<tr><td class="m">{ms}</td><td>{path}</td></tr>')
    tech_rows = "".join(sorted(rows))

    def section(title, sub, cards):
        return (f'<section><h2>{title}</h2><p class="sub">{sub}</p>'
                f'<div class="grid">{"".join(cards)}</div></section>')

    html = f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PHAI · Mappa del sito</title>
<style>
:root{{--bg:#0a0e18;--panel:#121829;--panel2:#1a2236;--border:#283149;--text:#e9ebf2;--muted:#8b94ab;--accent:#cba65c;--green:#3ddc97}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text);padding:24px 18px 60px}}
.wrap{{max-width:1080px;margin:0 auto}}
.top{{display:flex;align-items:center;gap:12px;margin-bottom:6px}}
.top img{{width:34px;height:34px}}
.top b{{font-size:20px;font-weight:800;letter-spacing:1px}}
.top i{{font-style:normal;color:var(--accent);font-size:11px;letter-spacing:2px}}
.lead{{color:var(--muted);font-size:14px;margin:4px 0 26px}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:28px}}
.actions a{{font-size:13px;font-weight:700;padding:9px 14px;border-radius:9px;background:var(--panel2);border:1px solid var(--border);color:var(--text);text-decoration:none}}
.actions a:hover{{border-color:var(--accent);color:var(--accent)}}
section{{margin-bottom:30px}}
h2{{font-size:15px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--accent);margin-bottom:2px}}
.sub{{color:var(--muted);font-size:12.5px;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
.sm-card{{background:linear-gradient(180deg,#161e30,#121829);border:1px solid var(--border);border-radius:12px;padding:13px 15px;text-decoration:none;color:var(--text);display:block;transition:.15s}}
a.sm-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.sm-t{{font-size:14px;font-weight:700}}
.sm-d{{font-size:12px;color:var(--muted);margin-top:4px;line-height:1.45}}
.sm-d code{{background:#0e1422;padding:1px 5px;border-radius:4px;color:#cfd6e6}}
.sm-langs{{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}}
.sm-langs .lang{{font-size:11px;font-weight:700;padding:4px 8px;border-radius:7px;background:#0e1422;border:1px solid var(--border);color:var(--accent);text-decoration:none}}
.sm-langs .lang:hover{{border-color:var(--accent)}}
details{{margin-top:6px;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:6px 14px}}
summary{{cursor:pointer;font-weight:700;font-size:13px;padding:8px 0;color:var(--text)}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 10px}}
td{{padding:5px 8px;border-bottom:1px solid var(--border);color:#cfd4de}}
td.m{{color:var(--green);font-weight:700;white-space:nowrap;width:120px}}
.footer{{color:var(--muted);font-size:12px;margin-top:24px}}
</style></head><body><div class="wrap">
<div class="top"><img src="/static/logo-mark.png" alt="PHAI"><b>PHAI <i>TRADING</i></b></div>
<div class="lead">Mappa del sito — tutte le pagine e i dati del prodotto, in un colpo d'occhio. Visibile solo a te (owner).</div>
<div class="actions"><a href="/">← Torna all'app</a><a href="/demo" target="_blank">Apri la Demo</a><a href="/landing" target="_blank">Apri la Landing</a></div>
{section("Pagine pubbliche / Marketing", "Cosa vede un visitatore. Le pagine marketing sono in 4 lingue.", marketing)}
{section("Checkout (un link per prodotto)", "Ogni SKU della scala di valore: singolo EA, pacchetti, portfolio, signals.", checkout_cards)}
{section("App cliente (dashboard)", "Le sezioni dell'app dopo il login.", app_pages)}
{section("Dati e download", "Scarica i risultati dei backtest e gli endpoint dati.", data_cards)}
<section><h2>Tutte le rotte tecniche</h2><p class="sub">Ogni endpoint del sistema (pagine + API + websocket).</p>
<details><summary>Mostra tutte le rotte ({len(rows)})</summary><table><tbody>{tech_rows}</tbody></table></details></section>
<div class="footer">Generata dal vivo dalle rotte dell'app · PHAI Trading</div>
</div></body></html>"""
    return HTMLResponse(html)


@app.post("/api/register")
async def api_register(request: Request):
    body = await request.json()
    try:
        uid = await auth.register(
            body.get("email", ""), body.get("password", ""), body.get("license_key", "")
        )
    except auth.AuthError as e:
        return JSONResponse({"error": e.msg}, status_code=e.status)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        auth.COOKIE_NAME,
        auth.create_session_token(uid),
        httponly=True,
        max_age=auth.SESSION_MAX_AGE,
        samesite="lax",
        secure=auth.COOKIE_SECURE,
    )
    return resp


@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    try:
        uid = await auth.login(body.get("email", ""), body.get("password", ""))
    except auth.AuthError as e:
        return JSONResponse({"error": e.msg}, status_code=e.status)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        auth.COOKIE_NAME,
        auth.create_session_token(uid),
        httponly=True,
        max_age=auth.SESSION_MAX_AGE,
        samesite="lax",
        secure=auth.COOKIE_SECURE,
    )
    return resp


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"ok": True})
    # gli attributi devono combaciare con set_cookie, o alcuni browser non lo cancellano
    resp.delete_cookie(auth.COOKIE_NAME, path="/", samesite="lax", secure=auth.COOKIE_SECURE)
    return resp


@app.get("/api/me")
async def api_me(user: User = Depends(auth.current_user)):
    plan = await _user_plan(user)
    return {"email": user.email, "plan": plan or None, "entitlements": entitlements.features(plan),
            "is_owner": _owner_id() is not None and user.id == _owner_id()}


@app.get("/api/signals")
async def get_signals(
    limit: int = 50,
    action: str = "",
    symbol: str = "",
    user: User = Depends(auth.current_user),
):
    # Prodotto SEGNALI: visibili solo agli abbonati con diritto (starter+).
    if not entitlements.can_signals(await _user_plan(user)):
        return []
    async with AsyncSession() as session:
        q = select(Signal).order_by(desc(Signal.id))
        if action:
            q = q.where(Signal.action == action)
        if symbol:
            q = q.where(Signal.symbol == symbol)
        q = _scope(q, Signal.user_id, user).limit(limit)
        rows = (await session.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "t": r.t.isoformat() if r.t else None,
            "symbol": r.symbol,
            "action": r.action,
            "pattern": r.pattern,
            "dir": r.dir,
            "reason": r.reason,
            "entry": r.entry,
            "sl": r.sl,
            "tp": r.tp,
            "lot": r.lot,
            "exit_price": r.exit_price,
            "pnl_pt": r.pnl_pt,
        }
        for r in rows
    ]


@app.get("/api/signals/radar")
async def signals_radar(user: User = Depends(auth.current_user)):
    """Radar segnali: UNA card per simbolo, sempre presente. Mostra la vicinanza al
    segnale (osc/verdetto 'siamo vicini/lontani') e, se c'è un trade APERTO, diventa
    'attivo' con entrata/TP/SL per tutto il periodo. Alimenta la tab Segnali."""
    if not entitlements.can_signals(await _user_plan(user)):
        return {"available": False, "cards": []}
    async with AsyncSession() as session:
        st_rows = (await session.execute(
            _scope(select(EaState), EaState.user_id, user).order_by(desc(EaState.t)).limit(300)
        )).scalars().all()
        sig_rows = (await session.execute(
            _scope(select(Signal), Signal.user_id, user).order_by(desc(Signal.id)).limit(300)
        )).scalars().all()
    state = {}
    for r in st_rows:
        if r.symbol and r.symbol not in state:
            state[r.symbol] = r
    last_sig = {}
    for r in sig_rows:
        if r.symbol and r.symbol not in last_sig:
            last_sig[r.symbol] = r
    cards = []
    for sym in sorted(set(state) | set(last_sig)):
        r = state.get(sym)
        bias = metrics.relval_bias(r.to_buy, r.to_sell) if r else None
        verdict = metrics.market_verdict_relval(bias) if bias else None
        ls = last_sig.get(sym)
        active = bool(ls and ls.action == "open")
        ea = catalog.EA_BY_ID.get(sym)
        card = {
            "symbol": sym,
            "name": ea["name"] if ea else sym,
            "osc": r.osc if r else None,
            "info": r.info if r else None,
            "verdict": verdict,
            "active": active,
            "t": (r.t.isoformat() if (r and r.t) else None),
        }
        if active:
            card["signal"] = {
                "dir": ls.dir, "entry": ls.entry, "tp": ls.tp, "sl": ls.sl,
                "lot": ls.lot, "t": ls.t.isoformat() if ls.t else None,
            }
        cards.append(card)
    return {"available": True, "cards": cards}


@app.get("/api/market")
async def get_market(user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        q = _scope(select(MarketSnapshot), MarketSnapshot.user_id, user).order_by(
            desc(MarketSnapshot.t)
        ).limit(1)
        row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        return {"bid": None, "ask": None, "spread_pts": None}
    return {
        "t": row.t.isoformat() if row.t else None,
        "bid": row.bid,
        "ask": row.ask,
        "spread_pts": row.spread_pts,
        "symbol": row.symbol,
    }


@app.get("/api/symbols")
async def get_symbols(user: User = Depends(auth.current_user)):
    """Elenco dei simboli navigabili. Non solo dai segnali (trade): include anche i
    simboli con stato strategia live (EaState), snapshot conto e backtest — cosi' i
    Reversione (EURGBP/GBPCHF) compaiono anche prima del primo trade."""
    syms: set[str] = set()
    async with AsyncSession() as session:
        scoped = [
            _scope(select(Signal.symbol).where(Signal.symbol.isnot(None)), Signal.user_id, user),
            _scope(select(EaState.symbol).where(EaState.symbol.isnot(None)), EaState.user_id, user),
            _scope(select(AccountSnapshot.symbol).where(AccountSnapshot.symbol.isnot(None)), AccountSnapshot.user_id, user),
        ]
        glob = [select(BacktestTrade.symbol).where(BacktestTrade.symbol.isnot(None))]
        for q in scoped + glob:
            rows = (await session.execute(q.distinct())).scalars().all()
            syms.update(s for s in rows if s)
    return sorted(syms)


def _bt_scope(q, symbol):
    q = q.where(BacktestTrade.exit_time.isnot(None))
    if symbol:
        q = q.where(BacktestTrade.symbol == symbol)
    return q


def _bt_agg():
    return (
        sa_func.count(BacktestTrade.id),
        sa_func.coalesce(sa_func.sum(BacktestTrade.pnl_pt), 0),
        sa_func.coalesce(sa_func.sum(BacktestTrade.pnl_money), 0),
        sa_func.sum(case((BacktestTrade.pnl_pt > 0, 1), else_=0)),
    )


def _row_stats(r):
    n, pt, money, w = r
    return {
        "trades": n or 0,
        "pnl_pt": round(float(pt or 0), 1),
        "pnl_money": round(float(money or 0), 2),
        "winrate": round((w or 0) / n * 100) if n else 0,
    }


INITIAL_CAPITAL = 10000.0   # deposito iniziale dei backtest (EUR)


async def _max_dd_pct(session, symbol, base=INITIAL_CAPITAL):
    """Max drawdown % sulla curva di balance reale (base + cumsum dei pnl_money,
    trade ordinati per uscita). Coincide col 'Balance Drawdown Maximal' del report MT5."""
    rows = (await session.execute(
        _bt_scope(select(BacktestTrade.pnl_money), symbol).order_by(BacktestTrade.exit_time)
    )).scalars().all()
    bal = peak = base
    maxdd = 0.0
    for p in rows:
        bal += float(p or 0)
        if bal > peak:
            peak = bal
        dd = (peak - bal) / peak if peak > 0 else 0.0
        if dd > maxdd:
            maxdd = dd
    return round(maxdd * 100, 1)


async def _overview_data(symbol: str = ""):
    """Costruisce i dati di backtest (totali + per-anno + capitale composto) per un
    simbolo (o tutti). Globale, non per-utente: è la prova pubblica del prodotto."""
    async with AsyncSession() as session:
        symbols = (
            await session.execute(
                select(BacktestTrade.symbol).where(BacktestTrade.symbol.isnot(None)).distinct()
            )
        ).scalars().all()
        if not symbols:
            return {"available": False, "symbols": []}
        totals = _row_stats(
            (await session.execute(_bt_scope(select(*_bt_agg()), symbol))).first()
        )
        years = (
            await session.execute(
                _bt_scope(
                    select(extract("year", BacktestTrade.exit_time).label("y"), *_bt_agg()),
                    symbol,
                ).group_by("y").order_by(desc("y"))
            )
        ).all()
        dd_o = await _max_dd_pct(session, symbol, INITIAL_CAPITAL * (1 if symbol else max(1, len([s for s in symbols if s]))))
    by_year = [{"year": int(y[0]), **_row_stats(y[1:])} for y in years]
    # Capitale iniziale: 10k PER CONTO. Vista singolo simbolo = 10k; vista combinata
    # (tutti i simboli) = 10k x numero di simboli (conti separati), cosi' la % non e' gonfiata.
    n_acc = 1 if symbol else max(1, len([s for s in symbols if s]))
    base = INITIAL_CAPITAL * n_acc
    # Capitale composto: ogni anno parte dal saldo di fine anno precedente.
    # growth_pct = PnL dell'anno / capitale d'inizio anno (= aumento sul capitale dell'anno prima).
    cap = base
    for yr in sorted(by_year, key=lambda e: e["year"]):   # cronologico
        yr["start_capital"] = round(cap, 2)
        yr["growth_pct"] = round(yr["pnl_money"] / cap * 100, 2) if cap else 0.0
        cap = round(cap + yr["pnl_money"], 2)
        yr["end_capital"] = cap
    # Crescita media annua composta (CAGR): rende confrontabile il "per anno".
    n_years = max(1, len(by_year))
    final_cap = base + totals["pnl_money"]
    cagr = ((final_cap / base) ** (1.0 / n_years) - 1) * 100 if base > 0 and final_cap > 0 else 0.0
    return {
        "available": True,
        "symbols": sorted(s for s in symbols if s),
        "initial_capital": base,
        "accounts": n_acc,
        "years": n_years,
        "totals": {
            **totals,
            "growth_pct": round(totals["pnl_money"] / base * 100, 2),
            "cagr_pct": round(cagr, 2),
            "max_dd_pct": dd_o,
            "avg_per_order": round(totals["pnl_money"] / totals["trades"], 2) if totals["trades"] else 0.0,
            "orders_per_year": round(totals["trades"] / n_years, 1),
        },
        "by_year": by_year,
        "reports": _symbol_reports(),
    }


@app.get("/api/backtest/overview")
async def backtest_overview(symbol: str = "", user: User = Depends(auth.current_user)):
    return await _overview_data(symbol)


@app.get("/api/public/backtest")
async def public_backtest(symbol: str = ""):
    """Overview backtest PUBBLICA (senza login) per la pagina Risultati."""
    return await _overview_data(symbol)


@app.get("/api/backtest/report/{symbol}/{fname}")
async def backtest_report(symbol: str, fname: str, user: User = Depends(auth.current_user)):
    """Serve i file del report MT5 originale (HTML + grafici PNG). Path-safe."""
    d = _report_dir(symbol)
    if not d:
        return JSONResponse({"error": "report non disponibile"}, status_code=404)
    path = os.path.join(d, os.path.basename(fname))   # basename: niente traversal
    if not os.path.isfile(path):
        return JSONResponse({"error": "file non trovato"}, status_code=404)
    return FileResponse(path)


@app.get("/api/public/report/{symbol}/{fname}")
async def public_report(symbol: str, fname: str):
    """Report MT5 originale (HTML + grafici), PUBBLICO senza login: è materiale
    di marketing che cliente o visitatore deve poter scaricare/vedere liberamente."""
    d = _report_dir(symbol)
    if not d:
        return JSONResponse({"error": "report non disponibile"}, status_code=404)
    path = os.path.join(d, os.path.basename(fname))   # basename: niente traversal
    if not os.path.isfile(path):
        return JSONResponse({"error": "file non trovato"}, status_code=404)
    return FileResponse(path)


@app.get("/api/public/track-record")
async def public_track_record():
    """Sintesi backtest PUBBLICA (senza login) per la landing: KPI + curva equity +
    dettaglio per simbolo. È materiale di prova/marketing, quindi non gated."""
    async with AsyncSession() as session:
        symbols = (
            await session.execute(select(BacktestTrade.symbol).where(BacktestTrade.symbol.isnot(None)).distinct())
        ).scalars().all()
        symbols = sorted(s for s in symbols if s)
        if not symbols:
            return {"available": False}
        totals = _row_stats((await session.execute(_bt_scope(select(*_bt_agg()), ""))).first())
        years = (
            await session.execute(
                _bt_scope(select(extract("year", BacktestTrade.exit_time).label("y"), *_bt_agg()), "")
                .group_by("y").order_by("y")
            )
        ).all()
        n_years = max(1, len(years))
        total_dd = await _max_dd_pct(session, "", INITIAL_CAPITAL * max(1, len(symbols)))
        per_sym = []
        for s in symbols:
            r = _row_stats((await session.execute(_bt_scope(select(*_bt_agg()), s))).first())
            final_s = INITIAL_CAPITAL + r["pnl_money"]
            cagr_s = ((final_s / INITIAL_CAPITAL) ** (1.0 / n_years) - 1) * 100 if final_s > 0 else 0.0
            per_sym.append({
                "symbol": s, "pnl_money": r["pnl_money"], "winrate": r["winrate"], "trades": r["trades"],
                "growth_pct": round(r["pnl_money"] / INITIAL_CAPITAL * 100, 2),   # totale su 16 anni
                "cagr_pct": round(cagr_s, 2),                                      # % media ANNUA composta
                "max_dd_pct": await _max_dd_pct(session, s),                       # max drawdown reale
                "avg_per_order": round(r["pnl_money"] / r["trades"], 2) if r["trades"] else 0.0,  # vincita media/ordine
                "orders_per_year": round(r["trades"] / n_years, 1),               # ordini medi/anno
            })
    by_year = [{"year": int(y[0]), **_row_stats(y[1:])} for y in years]
    base = INITIAL_CAPITAL * max(1, len(symbols))
    cap = base
    curve = []
    for yr in by_year:
        cap = round(cap + yr["pnl_money"], 2)
        curve.append({"year": yr["year"], "end_capital": cap})
    n_years = max(1, len(by_year))
    final = base + totals["pnl_money"]
    cagr = ((final / base) ** (1.0 / n_years) - 1) * 100 if base > 0 and final > 0 else 0.0
    return {
        "available": True, "initial_capital": base, "years": n_years, "symbols": symbols,
        "totals": {**totals, "growth_pct": round(totals["pnl_money"] / base * 100, 2), "cagr_pct": round(cagr, 2),
                   "max_dd_pct": total_dd,
                   "avg_per_order": round(totals["pnl_money"] / totals["trades"], 2) if totals["trades"] else 0.0,
                   "orders_per_year": round(totals["trades"] / n_years, 1)},
        "curve": curve, "per_symbol": per_sym, "reports": _symbol_reports(),
    }


@app.get("/api/backtest/year")
async def backtest_year(year: int, symbol: str = "", user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        q = _bt_scope(
            select(extract("month", BacktestTrade.exit_time).label("m"), *_bt_agg()), symbol
        ).where(extract("year", BacktestTrade.exit_time) == year)
        months = (await session.execute(q.group_by("m").order_by("m"))).all()
        # dettaglio per simbolo nell'anno (ordinato per PnL decrescente)
        sq = _bt_scope(
            select(BacktestTrade.symbol.label("s"), *_bt_agg()), symbol
        ).where(extract("year", BacktestTrade.exit_time) == year)
        syms = (
            await session.execute(
                sq.group_by("s").order_by(desc(sa_func.coalesce(sa_func.sum(BacktestTrade.pnl_money), 0)))
            )
        ).all()
    return {
        "year": year,
        "by_month": [{"month": int(m[0]), **_row_stats(m[1:])} for m in months],
        "by_symbol": [{"symbol": s[0], **_row_stats(s[1:])} for s in syms if s[0]],
    }


@app.get("/api/backtest/trades")
async def backtest_trades(
    year: int, month: int = 0, symbol: str = "", user: User = Depends(auth.current_user)
):
    async with AsyncSession() as session:
        q = _bt_scope(select(BacktestTrade), symbol).where(
            extract("year", BacktestTrade.exit_time) == year
        )
        if month:
            q = q.where(extract("month", BacktestTrade.exit_time) == month)
        rows = (await session.execute(q.order_by(BacktestTrade.exit_time))).scalars().all()
    return [
        {
            "symbol": r.symbol,
            "pattern": r.pattern,
            "dir": r.dir,
            "entry_time": r.entry_time.isoformat() if r.entry_time else None,
            "exit_time": r.exit_time.isoformat() if r.exit_time else None,
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "pnl_pt": r.pnl_pt,
            "pnl_money": r.pnl_money,
            "reason": r.reason,
            "duration_d": r.duration_d,
        }
        for r in rows
    ]


async def _market_state_data(symbol: str = ""):
    """Stato di mercato corrente: ultima barra, posizione vs MA, e per ogni feature
    valore/media/percentile/livello. Riusato da route, chat, notifiche e resoconti."""
    async with AsyncSession() as session:
        syms = (
            await session.execute(
                select(MarketFeature.symbol).where(MarketFeature.symbol.isnot(None)).distinct()
            )
        ).scalars().all()
        syms = sorted(s for s in syms if s)
        if not syms:
            return {"available": False, "symbols": []}
        if symbol and symbol not in syms:
            # simbolo richiesto senza feature (es. Reversione): niente fallback fuorviante,
            # la vista mostrera' solo il pannello oscillatore.
            return {"available": False, "symbols": syms, "symbol": symbol}
        sym = symbol if symbol in syms else syms[0]
        last = (
            await session.execute(
                select(MarketFeature).where(MarketFeature.symbol == sym)
                .order_by(desc(MarketFeature.t)).limit(1)
            )
        ).scalar_one_or_none()
        if not last:
            return {"available": False, "symbols": syms}
        total = (
            await session.execute(
                select(sa_func.count(MarketFeature.id)).where(MarketFeature.symbol == sym)
            )
        ).scalar() or 1

        async def stat(col, val):
            if val is None:
                return None
            avg = (
                await session.execute(
                    select(sa_func.avg(col)).where(MarketFeature.symbol == sym)
                )
            ).scalar()
            cnt = (
                await session.execute(
                    select(sa_func.count(MarketFeature.id)).where(
                        MarketFeature.symbol == sym, col <= val
                    )
                )
            ).scalar() or 0
            pct = round(cnt / total * 100)
            return {
                "value": round(float(val), 2),
                "avg": round(float(avg or 0), 2),
                "pct": pct,
                "level": "alto" if pct >= 70 else "basso" if pct <= 30 else "media",
            }

        FEAT_DESC = {
            "Volatilità": "Quanto si muove il prezzo. Alto = mercato agitato (movimenti ampi); basso = mercato calmo.",
            "Cluster": "Quanto le medie sono compatte e concordi. Alto = struttura ordinata, in trend; basso = medie sparse, mercato incerto/laterale.",
            "Velocità": "Quanto corre la struttura del prezzo (la sua pendenza). Alto = spinta forte; basso = quasi ferma.",
            "Accelerazione": "Se la spinta sta aumentando o calando. Alto = sta accelerando; basso = sta frenando.",
            "OrderScore": "Quanto la struttura è ordinata e direzionale. Alto = direzione pulita; basso = caos/laterale.",
        }
        feats = []
        for name, col, val in [
            ("Volatilità", MarketFeature.volatility, last.volatility),
            ("Cluster", MarketFeature.cluster, last.cluster),
            ("Velocità", MarketFeature.velocity, last.velocity),
            ("Accelerazione", MarketFeature.accel, last.accel),
            ("OrderScore", MarketFeature.order_score, last.order_score),
        ]:
            s = await stat(col, val)
            if s:
                feats.append({"name": name, "desc": FEAT_DESC.get(name, ""), **s})

        price_vs = []
        for ma, d in [("MA30", last.d_ma30), ("MA365", last.d_ma365), ("Median", last.d_med)]:
            if d is not None:
                price_vs.append({"ma": ma, "pos": "sopra" if d > 0 else "sotto", "dist": round(float(d), 2)})

    return {
        "available": True,
        "symbols": syms,
        "symbol": sym,
        "t": last.t.date().isoformat() if last.t else None,
        "close": last.close,
        "price_vs": price_vs,
        "features": feats,
        "bias": metrics.base_regime(last.d_ma365, last.velocity),
        "verdict": metrics.market_verdict_base(last.order_score, last.velocity),
    }


@app.get("/api/market-state")
async def market_state(symbol: str = "", user: User = Depends(auth.current_user)):
    """Stato di mercato per la tab Mercato (richiede login)."""
    return await _market_state_data(symbol)


async def _market_state_text(symbol: str = "") -> str:
    """Riassunto testuale dello stato di mercato live, per il contesto LLM (chat/resoconti)."""
    try:
        d = await _market_state_data(symbol)
    except Exception:
        return ""
    if not d.get("available"):
        return ""
    pv = ", ".join(f"{p['pos']} {p['ma']} ({p['dist']:+}%)" for p in d.get("price_vs", []))
    fs = "; ".join(f"{f['name']} {f['value']} (perc. {f['pct']}°, {f['level']})" for f in d.get("features", []))
    return (f"Stato di mercato LIVE {d['symbol']} (ultima barra {d['t']}, close {d['close']}): "
            f"prezzo {pv}. Feature [valore (percentile, livello)]: {fs}.")


@app.get("/api/push/key")
async def push_key(user: User = Depends(auth.current_user)):
    return {"key": os.getenv("VAPID_PUBLIC_KEY", "")}


@app.post("/api/admin/report")
async def admin_report(kind: str = "morning", user: User = Depends(auth.current_user)):
    """Genera e invia SUBITO il resoconto (mattino/sera), solo per l'owner. Per test e invio manuale."""
    oid = _owner_id()
    if oid is None or user.id != oid:
        return JSONResponse({"error": "non autorizzato"}, status_code=403)
    if kind not in _REPORT_HOURS:
        kind = "morning"
    await _generate_scheduled_report(kind)
    s = await _latest_summary(kind)
    return {"ok": True, "kind": kind, "content": s.content if s else None}


@app.post("/api/push/subscribe")
async def push_subscribe(request: Request, user: User = Depends(auth.current_user)):
    body = await request.json()
    endpoint = body.get("endpoint")
    keys = body.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return JSONResponse({"error": "Iscrizione non valida"}, status_code=400)
    async with AsyncSession() as session:
        existing = (
            await session.execute(
                select(PushSubscription).where(PushSubscription.endpoint == endpoint)
            )
        ).scalar_one_or_none()
        if existing:
            existing.user_id = user.id
            existing.p256dh = keys["p256dh"]
            existing.auth = keys["auth"]
        else:
            session.add(
                PushSubscription(
                    user_id=user.id,
                    endpoint=endpoint,
                    p256dh=keys["p256dh"],
                    auth=keys["auth"],
                )
            )
        await session.commit()
    return {"ok": True}


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(request: Request, user: User = Depends(auth.current_user)):
    body = await request.json()
    endpoint = body.get("endpoint")
    if endpoint:
        async with AsyncSession() as session:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.endpoint == endpoint)
            )
            await session.commit()
    return {"ok": True}


@app.get("/api/account")
async def get_account(user: User = Depends(auth.current_user)):
    """Stato del conto (balance/equity/margine come MetaTrader) + P/L flottante e
    profitto % per ciascun simbolo (dall'ultimo snapshot di ogni EA)."""
    async with AsyncSession() as session:
        rows = (
            await session.execute(
                _scope(select(AccountSnapshot), AccountSnapshot.user_id, user)
                .order_by(desc(AccountSnapshot.t)).limit(200)
            )
        ).scalars().all()
    if not rows:
        return {"available": False, "symbols": []}
    latest = rows[0]  # più recente in assoluto → dati conto account-wide
    per = {}
    for r in rows:
        if r.symbol and r.symbol not in per:
            per[r.symbol] = {
                "symbol": r.symbol,
                "profit": r.sym_profit,
                "pct": r.sym_pct,
                "open": r.sym_open,
            }
    return {
        "available": True,
        "t": latest.t.isoformat() if latest.t else None,
        "balance": latest.balance,
        "equity": latest.equity,
        "margin": latest.margin,
        "free_margin": latest.free_margin,
        "margin_level": latest.margin_level,
        "profit": latest.profit,
        "symbols": sorted(per.values(), key=lambda x: x["symbol"]),
    }


@app.get("/api/equity-history")
async def equity_history(user: User = Depends(auth.current_user)):
    """Serie storica leggera di equity/balance nel tempo (grafico 'andamento conto')."""
    async with AsyncSession() as session:
        rows = (await session.execute(
            _scope(select(EquityPoint), EquityPoint.user_id, user)
            .order_by(EquityPoint.t).limit(3000)
        )).scalars().all()
    return {"points": [
        {"t": r.t.isoformat() if r.t else None, "equity": r.equity, "balance": r.balance}
        for r in rows
    ]}


@app.get("/api/price-history")
async def price_history(symbol: str = "", user: User = Depends(auth.current_user)):
    """Barre OHLC (D1) del cross per il grafico navigabile. Globale: il prezzo è uguale
    per tutti i clienti, quindi una sola serie per simbolo."""
    sym = (symbol or "").upper()
    if not sym:
        return {"symbol": sym, "bars": []}
    async with AsyncSession() as session:
        rows = (await session.execute(
            select(PriceBar).where(PriceBar.symbol == sym).order_by(PriceBar.t).limit(2000)
        )).scalars().all()
    return {"symbol": sym, "bars": [
        {"t": r.t.isoformat() if r.t else None, "o": r.o, "h": r.h, "l": r.l, "c": r.c}
        for r in rows
    ]}


@app.get("/api/trade-markers")
async def trade_markers(symbol: str = "", user: User = Depends(auth.current_user)):
    """Entrate/uscite dell'utente sul grafico del cross (scoped per tenant: ognuno vede
    solo i PROPRI trade, sovrapposti al prezzo che è comune a tutti)."""
    sym = (symbol or "").upper()
    if not sym:
        return {"markers": []}
    async with AsyncSession() as session:
        rows = (await session.execute(
            _scope(select(Signal), Signal.user_id, user)
            .where(Signal.symbol == sym, Signal.action.in_(["open", "close"]))
            .order_by(Signal.t).limit(500)
        )).scalars().all()
    out = []
    for r in rows:
        if not r.t:
            continue
        out.append({"day": r.t.date().isoformat(), "action": r.action,
                    "dir": (r.dir or "").upper(), "pnl": r.pnl_pt})
    return {"markers": out}


@app.get("/api/strategy-state")
async def get_strategy_state(user: User = Depends(auth.current_user)):
    """Stato LIVE delle strategie Reversione: oscillatore (0-100) + nota 'dove siamo',
    dall'ultimo invio di ogni EA (aggiornato ~ogni 15s)."""
    async with AsyncSession() as session:
        rows = (
            await session.execute(
                _scope(select(EaState), EaState.user_id, user)
                .order_by(desc(EaState.t)).limit(200)
            )
        ).scalars().all()
    per = {}
    for r in rows:
        if r.symbol and r.symbol not in per:
            per[r.symbol] = {
                "symbol": r.symbol,
                "osc": r.osc,
                "info": r.info,
                "dist": r.dist,
                "vol": r.vol,
                "to_buy": r.to_buy,
                "to_sell": r.to_sell,
                "bars_out": r.bars_out,
                "bias": metrics.relval_bias(r.to_buy, r.to_sell),
                "verdict": metrics.market_verdict_relval(metrics.relval_bias(r.to_buy, r.to_sell)),
                "t": r.t.isoformat() if r.t else None,
            }
    return {
        "available": bool(per),
        "symbols": sorted(per.values(), key=lambda x: x["symbol"]),
    }


@app.get("/api/stats")
async def get_stats(symbol: str = "", user: User = Depends(auth.current_user)):
    def _scoped(q):
        q = _scope(q, Signal.user_id, user)
        return q.where(Signal.symbol == symbol) if symbol else q

    async with AsyncSession() as session:
        async def cnt(*conds):
            q = select(sa_func.count(Signal.id))
            for c in conds:
                q = q.where(c)
            return (await session.execute(_scoped(q))).scalar() or 0

        total = await cnt()
        opens = await cnt(Signal.action == "open")
        closes = await cnt(Signal.action == "close")
        skips = await cnt(Signal.action == "skip")
        pnl_sum = (
            await session.execute(
                _scoped(
                    select(sa_func.coalesce(sa_func.sum(Signal.pnl_pt), 0)).where(
                        Signal.action == "close"
                    )
                )
            )
        ).scalar() or 0
    return {
        "total": total,
        "open": opens,
        "close": closes,
        "skip": skips,
        "pnl_pt": round(float(pnl_sum), 1),
    }


@app.post("/api/conversations")
async def create_conversation(user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        conv = Conversation(user_id=user.id, title="Nuova conversazione")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
    return {"id": conv.id, "title": conv.title}


@app.get("/api/conversations")
async def list_conversations(user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        rows = (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user.id)
                .order_by(desc(Conversation.updated_at))
                .limit(100)
            )
        ).scalars().all()
    return [
        {
            "id": c.id,
            "title": c.title or "Conversazione",
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in rows
    ]


@app.get("/api/conversations/{conv_id}/messages")
async def conversation_messages(conv_id: int, user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv or conv.user_id != user.id:
            return JSONResponse({"error": "Conversazione non trovata"}, status_code=404)
        rows = (
            await session.execute(
                select(ChatHistory)
                .where(ChatHistory.conversation_id == conv_id)
                .order_by(ChatHistory.id)
            )
        ).scalars().all()
    return {
        "id": conv_id,
        "title": conv.title or "Conversazione",
        "messages": [
            {"q": r.question, "a": r.answer, "t": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ],
    }


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: int, user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        conv = await session.get(Conversation, conv_id)
        if conv and conv.user_id == user.id:
            await session.execute(
                delete(ChatHistory).where(ChatHistory.conversation_id == conv_id)
            )
            await session.delete(conv)
            await session.commit()
    return {"ok": True}


@app.get("/api/chat-quota")
async def chat_quota(user: User = Depends(auth.current_user)):
    """Quota messaggi giornaliera del tier free (per il contatore fisso in chat).
    Paid/premium (o tetto 0) = illimitato."""
    tier = await _user_tier(user)
    if tier != "free" or FREE_DAILY_MSGS <= 0:
        return {"limited": False}
    used = await _free_msgs_used_today(user.id)
    return {
        "limited": True,
        "used": used,
        "limit": FREE_DAILY_MSGS,
        "remaining": max(0, FREE_DAILY_MSGS - used),
    }


@app.post("/api/chat")
async def chat(request: Request, user: User = Depends(auth.current_user)):
    body = await request.json()
    question = body.get("question", "").strip()
    symbol = (body.get("symbol") or "").strip()
    conversation_id = body.get("conversation_id")
    lang = (body.get("lang") or "it").strip().lower()
    if lang not in ("it", "en", "fr", "es"):
        lang = "it"
    if not question:
        return JSONResponse({"error": "Domanda vuota"}, status_code=400)

    # Digest completo di metriche dal DB: l'assistente riceve numeri già calcolati
    # (conto, performance per simbolo/pattern, periodo, ultimi segnali) → niente
    # numeri inventati. La firma include l'ultimo snapshot conto, così la cache si
    # invalida quando i dati (anche il P/L flottante) cambiano.
    tier = await _user_tier(user)             # free|paid|premium → modello LLM per piano
    digest = await metrics.build_digest(symbol, user.id, _owner_id())
    context = digest["text"]
    context_sig = digest["sig"] + ":" + lang + ":" + tier  # cache distinta per utente, lingua e modello
    recent_count = digest["recent_count"]

    # Domande comuni → riassunto condiviso precalcolato, 0 quota LLM.
    # Solo vista globale e in italiano (il riassunto precalcolato è in italiano).
    precomputed = None
    if lang == "it" and not symbol and _is_common_question(question):
        precomputed = await _latest_summary("perf_today")

    # Tetto giornaliero del tier free: se esaurito (e non è una domanda comune gratis),
    # rispondi con l'invito all'upgrade senza consumare quota LLM.
    limit_msg = None
    if tier == "free" and precomputed is None and FREE_DAILY_MSGS > 0:
        if await _free_msgs_used_today(user.id) >= FREE_DAILY_MSGS:
            limit_msg = (
                f"⛔ Hai usato i tuoi **{FREE_DAILY_MSGS} messaggi gratuiti di oggi**.\n\n"
                "Attiva **Assistente + Segnali** (5€/mese) — o un qualsiasi pacchetto — per messaggi "
                "**illimitati**, l'assistente più potente e i **segnali con notifica push**. "
                "Il limite gratuito si azzera a mezzanotte."
            )

    async def event_stream():
        if limit_msg is not None:
            yield "data: " + json.dumps({"text": limit_msg}) + "\n\n"
            yield "data: __DONE__\n\n"
            return   # niente LLM, niente salvataggio: non consuma quota
        # Risposta precalcolata/cache → un solo evento {"text": ...}.
        # Risposta LLM → streaming: tanti eventi {"delta": pezzo} man mano che arrivano.
        # Ogni evento è un JSON: preserva newline e caratteri speciali nel framing SSE.
        if precomputed is not None:
            full = precomputed
            yield "data: " + json.dumps({"text": full}) + "\n\n"
        else:
            parts = []
            async for chunk in llm_worker.submit_stream(question, context, context_sig, user.id, lang, tier):
                parts.append(chunk)
                yield "data: " + json.dumps({"delta": chunk}) + "\n\n"
            full = "".join(parts)
        yield "data: __DONE__\n\n"

        async with AsyncSession() as session:
            ch = ChatHistory(
                user_id=user.id,
                conversation_id=conversation_id,
                question=question,
                answer=full,
                context={"signals_count": recent_count, "source": "summary" if precomputed else "llm", "symbol": symbol or None},
            )
            session.add(ch)
            if conversation_id:
                conv = await session.get(Conversation, conversation_id)
                if conv and conv.user_id == user.id:
                    conv.updated_at = datetime.utcnow()
                    if not conv.title or conv.title == "Nuova conversazione":
                        conv.title = question[:80]
            await session.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    token = ws.cookies.get(auth.COOKIE_NAME)
    uid = auth.verify_session_token(token) if token else None
    if not uid:
        await ws.close(code=1008)  # policy violation
        return
    await ws.accept()
    clients[ws] = uid
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.pop(ws, None)
