import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime

from sqlalchemy import select, desc, delete, func as sa_func

from db import (
    init_db,
    AsyncSession,
    Signal,
    ChatHistory,
    MarketSnapshot,
    User,
    DailySummary,
    AccountSnapshot,
    Conversation,
)
from mt5_bridge import LogTailer
import llm_worker
import auth
import metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("papp")

clients: set[WebSocket] = set()

SUMMARY_REFRESH_MIN = int(os.getenv("SUMMARY_REFRESH_MIN", "30"))

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


async def on_signal(data: dict):
    if data.get("action") == "account":
        async with AsyncSession() as session:
            session.add(AccountSnapshot(
                t=data.get("t"),
                symbol=data.get("symbol"),
                balance=data.get("balance"),
                equity=data.get("equity"),
                margin=data.get("margin"),
                free_margin=data.get("free_margin"),
                margin_level=data.get("margin_level"),
                profit=data.get("profit"),
                sym_profit=data.get("sym_profit"),
                sym_pct=data.get("sym_pct"),
                sym_open=data.get("sym_open"),
            ))
            await session.commit()
        return

    if data.get("action") == "market":
        async with AsyncSession() as session:
            snap = MarketSnapshot(
                t=data.get("t"),
                symbol=data.get("symbol") or "EURUSD",
                bid=data.get("bid"),
                ask=data.get("ask"),
                spread_pts=data.get("spread_pts"),
            )
            session.add(snap)
            await session.commit()
        return

    async with AsyncSession() as session:
        sig = Signal(
            t=data.get("t"),
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
    dead = set()
    for ws in clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)
    log.info("Signal #%d: %s p%d %s", sig.id, sig.action, sig.pattern or 0, sig.dir or "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("DB inizializzato")
    llm_worker.start_worker()
    tailer = LogTailer(on_signal)
    task = asyncio.create_task(tailer.start())
    log.info("LogTailer avviato su: %s", tailer.path)
    summary_task = asyncio.create_task(_summary_loop())
    log.info("Loop riassunti avviato (ogni %d min)", SUMMARY_REFRESH_MIN)
    yield
    tailer.stop()
    task.cancel()
    summary_task.cancel()
    llm_worker.stop_worker()


app = FastAPI(title="PAPP EA Chat", version="1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token and auth.verify_session_token(token):
        return HTMLResponse(open("templates/index.html").read())
    return HTMLResponse(open("templates/login.html").read())


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
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/api/me")
async def api_me(user: User = Depends(auth.current_user)):
    return {"email": user.email}


@app.get("/api/signals")
async def get_signals(
    limit: int = 50,
    action: str = "",
    symbol: str = "",
    user: User = Depends(auth.current_user),
):
    async with AsyncSession() as session:
        q = select(Signal).order_by(desc(Signal.id))
        if action:
            q = q.where(Signal.action == action)
        if symbol:
            q = q.where(Signal.symbol == symbol)
        q = q.limit(limit)
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


@app.get("/api/market")
async def get_market(user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        q = select(MarketSnapshot).order_by(desc(MarketSnapshot.id)).limit(1)
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
    """Elenco dei simboli presenti nei segnali (per le tab di navigazione)."""
    async with AsyncSession() as session:
        rows = (
            await session.execute(
                select(Signal.symbol).where(Signal.symbol.isnot(None)).distinct()
            )
        ).scalars().all()
    return sorted(s for s in rows if s)


@app.get("/api/account")
async def get_account(user: User = Depends(auth.current_user)):
    """Stato del conto (balance/equity/margine come MetaTrader) + P/L flottante e
    profitto % per ciascun simbolo (dall'ultimo snapshot di ogni EA)."""
    async with AsyncSession() as session:
        rows = (
            await session.execute(
                select(AccountSnapshot).order_by(desc(AccountSnapshot.id)).limit(200)
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


@app.get("/api/stats")
async def get_stats(symbol: str = "", user: User = Depends(auth.current_user)):
    def _scoped(q):
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


@app.post("/api/chat")
async def chat(request: Request, user: User = Depends(auth.current_user)):
    body = await request.json()
    question = body.get("question", "").strip()
    symbol = (body.get("symbol") or "").strip()
    conversation_id = body.get("conversation_id")
    if not question:
        return JSONResponse({"error": "Domanda vuota"}, status_code=400)

    # Digest completo di metriche dal DB: l'assistente riceve numeri già calcolati
    # (conto, performance per simbolo/pattern, periodo, ultimi segnali) → niente
    # numeri inventati. La firma include l'ultimo snapshot conto, così la cache si
    # invalida quando i dati (anche il P/L flottante) cambiano.
    digest = await metrics.build_digest(symbol)
    context = digest["text"]
    context_sig = digest["sig"]
    recent_count = digest["recent_count"]

    # Domande comuni → riassunto condiviso precalcolato, 0 quota LLM.
    # (solo per la vista globale: il riassunto precalcolato non è per-simbolo)
    precomputed = None
    if not symbol and _is_common_question(question):
        precomputed = await _latest_summary("perf_today")

    async def event_stream():
        if precomputed is not None:
            full = precomputed
        else:
            full = await llm_worker.submit(question, context, context_sig, user.id)
        # Risposta inviata come singolo evento JSON: preserva newline e caratteri
        # speciali, che con "data: {full}" romperebbero il framing SSE (le righe
        # successive alla prima venivano scartate dal client).
        yield "data: " + json.dumps({"text": full}) + "\n\n"
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
    if not token or not auth.verify_session_token(token):
        await ws.close(code=1008)  # policy violation
        return
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)
