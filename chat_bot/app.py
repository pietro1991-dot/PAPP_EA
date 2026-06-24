import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, desc, func as sa_func

from db import (
    init_db,
    AsyncSession,
    Signal,
    ChatHistory,
    MarketSnapshot,
    User,
    DailySummary,
)
from mt5_bridge import LogTailer
import llm_worker
import auth

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


async def _build_context():
    """Contesto condiviso (segnali recenti + statistiche) usato sia dalla chat sia
    dal riassunto. Ritorna (context_str, last_signal_id, recent_count)."""
    async with AsyncSession() as session:
        recent = (
            (await session.execute(select(Signal).order_by(desc(Signal.id)).limit(20)))
            .scalars()
            .all()
        )
        stats = (
            await session.execute(
                select(
                    sa_func.count(Signal.id),
                    sa_func.coalesce(sa_func.sum(Signal.pnl_pt), 0),
                ).where(Signal.action == "close")
            )
        ).first()

    ctx_lines = ["Segnali recenti (ultimi 20):"]
    for s in recent[:10]:
        line = f"[{s.action}] pattern={s.pattern} dir={s.dir}"
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
    context, last_id, n = await _build_context()
    if n == 0:
        return
    question = (
        "Riassumi in massimo 3 frasi l'andamento della strategia oggi: numero di "
        "operazioni, PnL complessivo e il pattern più attivo."
    )
    answer = await llm_worker.submit(question, context, f"summary{last_id}")
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
    if data.get("action") == "market":
        async with AsyncSession() as session:
            snap = MarketSnapshot(
                t=data.get("t"),
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
    limit: int = 50, action: str = "", user: User = Depends(auth.current_user)
):
    async with AsyncSession() as session:
        q = select(Signal).order_by(desc(Signal.id))
        if action:
            q = q.where(Signal.action == action)
        q = q.limit(limit)
        rows = (await session.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "t": r.t.isoformat() if r.t else None,
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


@app.get("/api/stats")
async def get_stats(user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        total = (await session.execute(select(sa_func.count(Signal.id)))).scalar() or 0
        opens = (
            await session.execute(
                select(sa_func.count(Signal.id)).where(Signal.action == "open")
            )
        ).scalar() or 0
        closes = (
            await session.execute(
                select(sa_func.count(Signal.id)).where(Signal.action == "close")
            )
        ).scalar() or 0
        skips = (
            await session.execute(
                select(sa_func.count(Signal.id)).where(Signal.action == "skip")
            )
        ).scalar() or 0
        pnl_sum = (
            await session.execute(
                select(sa_func.coalesce(sa_func.sum(Signal.pnl_pt), 0)).where(
                    Signal.action == "close"
                )
            )
        ).scalar() or 0
    return {"total": total, "open": opens, "close": closes, "skip": skips, "pnl_pt": round(float(pnl_sum), 1)}


@app.post("/api/chat")
async def chat(request: Request, user: User = Depends(auth.current_user)):
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "Domanda vuota"}, status_code=400)

    context, last_id, recent_count = await _build_context()
    # Firma del contesto per la cache: cambia ad ogni nuovo segnale, così le
    # risposte cachate restano valide finché il quadro dei segnali non cambia.
    context_sig = f"sig{last_id}"

    # Domande comuni → riassunto condiviso precalcolato, 0 quota LLM.
    precomputed = None
    if _is_common_question(question):
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
                question=question,
                answer=full,
                context={"signals_count": recent_count, "source": "summary" if precomputed else "llm"},
            )
            session.add(ch)
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
