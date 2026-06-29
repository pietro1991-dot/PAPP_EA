import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime

from sqlalchemy import select, desc, delete, extract, case, or_, func as sa_func

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
            out.setdefault(m.group(1), f"/api/backtest/report/{m.group(1)}/{os.path.basename(htmls[0])}")
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
    gli accessi (segnali/EA/chatbot tornano al livello demo)."""
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


async def process_event(data: dict, user_id: int | None = None):
    """Ingestione di un evento dell'EA (da bridge locale o da /api/ea/ingest),
    taggato con il tenant `user_id`. Gestisce account, market e segnali."""
    if data.get("action") == "account":
        async with AsyncSession() as session:
            session.add(AccountSnapshot(
                t=data.get("t"),
                user_id=user_id,
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
                user_id=user_id,
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
            title = f"🟢 Ordine aperto — {sym} {pat} {dirs}".strip()
            body = ""
            if sig.entry:
                body += f"Entrata @{sig.entry:.5f}. "
            if sig.reason:
                body += sig.reason
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


def _serve_page(name: str, request: Request) -> HTMLResponse:
    """Serve la pagina nella lingua del visitatore (file <name>.<lang>.html, fallback IT)
    e inietta il selettore lingua. Le traduzioni si generano con pipeline/translate_pages.py."""
    lang = _req_lang(request)
    path = f"templates/{name}.{lang}.html" if lang != "it" else f"templates/{name}.html"
    if not os.path.exists(path):
        path = f"templates/{name}.html"
        lang = "it"
    html_c = open(path, encoding="utf-8").read().replace("</body>", _lang_selector(lang) + "</body>", 1)
    resp = HTMLResponse(html_c)
    if (request.query_params.get("lang") or "").lower() in PAGE_LANGS:
        resp.set_cookie("lang", lang, max_age=31536000, samesite="lax")
    return resp


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token and auth.verify_session_token(token):
        return HTMLResponse(open("templates/index.html").read())
    return _serve_page("landing", request)   # pubblico → landing marketing multilingua


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(open("templates/login.html").read())


@app.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    """Squeeze page HVCO (opt-in report) per il traffico freddo degli annunci."""
    return _serve_page("squeeze", request)


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
            plan = _plan_from_paypal(data.get("plan_id")) or (plan_req if plan_req in ("starter", "pro") else "pro")
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
            # Lifetime = funzioni Pro senza scadenza
            res = await licensing.issue_license(email, plan="pro", source="paypal", external_id=order_id)
            return {"ok": True, "key": res["key"]}
    return JSONResponse({"ok": False, "reason": "no_id"}, status_code=400)


@app.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request):
    return _serve_page("checkout", request)


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
    return {"email": user.email, "plan": plan or None, "entitlements": entitlements.features(plan)}


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


@app.get("/api/market")
async def get_market(user: User = Depends(auth.current_user)):
    async with AsyncSession() as session:
        q = _scope(select(MarketSnapshot), MarketSnapshot.user_id, user).order_by(
            desc(MarketSnapshot.id)
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
    """Elenco dei simboli presenti nei segnali (per le tab di navigazione)."""
    async with AsyncSession() as session:
        q = _scope(select(Signal.symbol).where(Signal.symbol.isnot(None)), Signal.user_id, user)
        rows = (await session.execute(q.distinct())).scalars().all()
    return sorted(s for s in rows if s)


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


@app.get("/api/backtest/overview")
async def backtest_overview(symbol: str = "", user: User = Depends(auth.current_user)):
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
        },
        "by_year": by_year,
        "reports": _symbol_reports(),
    }


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
        per_sym = []
        for s in symbols:
            r = _row_stats((await session.execute(_bt_scope(select(*_bt_agg()), s))).first())
            per_sym.append({
                "symbol": s, "pnl_money": r["pnl_money"], "winrate": r["winrate"],
                "growth_pct": round(r["pnl_money"] / INITIAL_CAPITAL * 100, 2),
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
        "totals": {**totals, "growth_pct": round(totals["pnl_money"] / base * 100, 2), "cagr_pct": round(cagr, 2)},
        "curve": curve, "per_symbol": per_sym,
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


@app.get("/api/market-state")
async def market_state(symbol: str = "", user: User = Depends(auth.current_user)):
    """Stato di mercato corrente di un simbolo: ultima barra, posizione vs MA, e
    per ogni feature valore/media/percentile/livello. Per la tab Mercato."""
    async with AsyncSession() as session:
        syms = (
            await session.execute(
                select(MarketFeature.symbol).where(MarketFeature.symbol.isnot(None)).distinct()
            )
        ).scalars().all()
        syms = sorted(s for s in syms if s)
        if not syms:
            return {"available": False, "symbols": []}
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
                feats.append({"name": name, **s})

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
    }


@app.get("/api/push/key")
async def push_key(user: User = Depends(auth.current_user)):
    return {"key": os.getenv("VAPID_PUBLIC_KEY", "")}


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
                .order_by(desc(AccountSnapshot.id)).limit(200)
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

    async def event_stream():
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
