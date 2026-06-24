import json
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, desc, func as sa_func

from db import init_db, AsyncSession, Signal, ChatHistory, MarketSnapshot
from mt5_bridge import LogTailer
from chat_logic import ask_ollama_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("papp")

clients: set[WebSocket] = set()


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
    tailer = LogTailer(on_signal)
    task = asyncio.create_task(tailer.start())
    log.info("LogTailer avviato su: %s", tailer.path)
    yield
    tailer.stop()
    task.cancel()


app = FastAPI(title="PAPP EA Chat", version="1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(open("templates/index.html").read())


@app.get("/api/signals")
async def get_signals(limit: int = 50, action: str = ""):
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
async def get_market():
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
async def get_stats():
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
async def chat(request: Request):
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "Domanda vuota"}, status_code=400)

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
        ctx_lines.append(
            f"Totali: {stats[0]} chiusure, PnL={float(stats[1]):+.1f}pt"
        )

    context = "\n".join(ctx_lines)

    async def event_stream():
        full = ""
        async for chunk in ask_ollama_stream(question, context):
            full += chunk
            yield f"data: {chunk}\n\n"
        yield f"data: __DONE__\n\n"

        async with AsyncSession() as session:
            ch = ChatHistory(question=question, answer=full, context={"signals_count": len(recent)})
            session.add(ch)
            await session.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)
