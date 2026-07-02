"""Layer LLM: isola l'endpoint gratuito (quota condivisa) dietro una coda con un
solo worker, un rate limiter token-bucket e una cache (LRU in memoria + DB).

Obiettivo: molti utenti web, UNA sola quota LLM gratuita. La concorrenza verso
l'LLM è sempre 1; le domande ripetute sono servite dalla cache senza toccare la
quota. Gli endpoint NON chiamano mai `ask()` direttamente: usano `submit()`.
"""
import asyncio
import hashlib
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import select

from db import AsyncSession, LlmCache
from chat_logic import ask, ask_stream, resolve_llm

log = logging.getLogger("papp.llm")

LLM_RPM = int(os.getenv("LLM_RPM", "15"))         # chiamate/minuto verso l'LLM (globale)
LLM_USER_RPM = int(os.getenv("LLM_USER_RPM", "5"))  # domande/minuto per utente
CACHE_MAX = int(os.getenv("CACHE_MAX", "500"))    # voci LRU in memoria
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "2"))     # tentativi extra su risposta vuota
LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "2"))  # attesa tra i tentativi (s)
# Modello di riserva se il primario fallisce anche dopo i retry (es. deepseek va in 500).
# Vuoto = nessun fallback. Garantisce una risposta anche durante i down del primario.
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "deepseek-v4-flash-free").strip()
# Timeout breve sul primario: se non risponde entro questo tempo, passa al fallback.
LLM_PRIMARY_TIMEOUT = float(os.getenv("LLM_PRIMARY_TIMEOUT", "10"))

FALLBACK = (
    "Il servizio AI è momentaneamente al limite. Riprova tra qualche minuto."
)
BUSY = "Hai già una domanda in corso: attendi la risposta prima di inviarne un'altra."
RATE = "Hai raggiunto il limite di domande al minuto. Riprova tra poco."


@dataclass
class _Job:
    question: str
    context: str
    key: str
    future: "asyncio.Future | None" = None
    lang: str = "it"
    tier: str = "free"                        # free|paid|premium → modello LLM per piano
    stream_q: "asyncio.Queue | None" = None   # se valorizzata → job in streaming


class TokenBucket:
    """Rate limiter: rilascia al più `rpm` permessi al minuto, a ritmo costante."""

    def __init__(self, rpm: int):
        self.capacity = max(1, rpm)
        self.tokens = float(self.capacity)
        self.rate = self.capacity / 60.0  # token al secondo
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            while True:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity, self.tokens + (now - self.updated) * self.rate
                )
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) / self.rate)

    def try_acquire(self) -> bool:
        """Variante non bloccante: consuma un permesso se disponibile, altrimenti
        ritorna False senza attendere. Per il rate limit per-utente."""
        now = time.monotonic()
        self.tokens = min(
            self.capacity, self.tokens + (now - self.updated) * self.rate
        )
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


# --- stato modulo (singleton in-process) ---------------------------------
_queue: "asyncio.Queue[_Job]" = asyncio.Queue()
_bucket = TokenBucket(LLM_RPM)
_lru: "OrderedDict[str, str]" = OrderedDict()
_task: asyncio.Task | None = None
_user_inflight: set[int] = set()              # utenti con una richiesta LLM in volo
_user_buckets: dict[int, TokenBucket] = {}    # rate limit per-utente


def _cache_key(question: str, context_sig: str | None) -> str:
    norm = " ".join(question.lower().split())
    raw = norm + "|" + (context_sig or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _lru_get(key: str):
    if key in _lru:
        _lru.move_to_end(key)
        return _lru[key]
    return None


def _lru_put(key: str, value: str):
    _lru[key] = value
    _lru.move_to_end(key)
    while len(_lru) > CACHE_MAX:
        _lru.popitem(last=False)


async def _db_get(key: str):
    async with AsyncSession() as session:
        row = (
            await session.execute(select(LlmCache).where(LlmCache.cache_key == key))
        ).scalar_one_or_none()
        if row:
            row.hits += 1
            await session.commit()
            return row.answer
    return None


async def _db_put(key: str, question: str, answer: str):
    async with AsyncSession() as session:
        # evita race su cache_key unique: ricontrolla prima di inserire
        exists = (
            await session.execute(select(LlmCache.id).where(LlmCache.cache_key == key))
        ).scalar_one_or_none()
        if exists:
            return
        session.add(LlmCache(cache_key=key, question=question, answer=answer))
        try:
            await session.commit()
        except Exception:
            await session.rollback()


async def submit(
    question: str,
    context: str,
    context_sig: str | None,
    user_id: int | None = None,
    lang: str = "it",
    tier: str = "free",
) -> str:
    """Punto d'ingresso per gli endpoint. Cache-hit → risposta immediata (0 quota);
    altrimenti applica la fairness per-utente, accoda e attende il worker.
    Non solleva mai: su errore ritorna un messaggio di fallback."""
    key = _cache_key(question, context_sig)

    # 1) Cache (memoria → DB): hit = gratis e senza limiti per-utente.
    hit = _lru_get(key)
    if hit is not None:
        return hit
    hit = await _db_get(key)
    if hit is not None:
        _lru_put(key, hit)
        return hit

    # 2) Serve l'LLM: applica la fairness per-utente.
    if user_id is not None:
        if user_id in _user_inflight:
            return BUSY
        bucket = _user_buckets.setdefault(user_id, TokenBucket(LLM_USER_RPM))
        if not bucket.try_acquire():
            return RATE
        _user_inflight.add(user_id)

    # 3) Accoda e attendi.
    try:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        await _queue.put(_Job(question=question, context=context, key=key, future=fut, lang=lang, tier=tier))
        return await fut
    finally:
        if user_id is not None:
            _user_inflight.discard(user_id)


async def submit_stream(
    question: str,
    context: str,
    context_sig: str | None,
    user_id: int | None = None,
    lang: str = "it",
    tier: str = "free",
):
    """Come submit() ma in streaming: async-generator che produce i pezzi (delta) della
    risposta man mano. Mantiene cache, fairness per-utente, coda e rate-limit globale.
    Cache-hit / BUSY / RATE → un singolo chunk (testo completo)."""
    key = _cache_key(question, context_sig)

    # 1) Cache: hit = un solo chunk col testo completo.
    hit = _lru_get(key)
    if hit is None:
        hit = await _db_get(key)
        if hit is not None:
            _lru_put(key, hit)
    if hit is not None:
        yield hit
        return

    # 2) Fairness per-utente.
    if user_id is not None:
        if user_id in _user_inflight:
            yield BUSY
            return
        bucket = _user_buckets.setdefault(user_id, TokenBucket(LLM_USER_RPM))
        if not bucket.try_acquire():
            yield RATE
            return
        _user_inflight.add(user_id)

    # 3) Accoda un job di streaming e drena la sua coda fino al sentinel None.
    try:
        q: asyncio.Queue = asyncio.Queue()
        await _queue.put(_Job(question=question, context=context, key=key, lang=lang, tier=tier, stream_q=q))
        while True:
            chunk = await q.get()
            if chunk is None:
                break
            yield chunk
    finally:
        if user_id is not None:
            _user_inflight.discard(user_id)


async def _handle_stream_job(job: _Job):
    """Eseguito dal worker: streamma dall'LLM nella coda del job, accumula la risposta
    completa per la cache, e chiude con un sentinel None."""
    q = job.stream_q
    # un'altra richiesta identica potrebbe aver popolato la cache nel frattempo
    hit = _lru_get(job.key)
    if hit is not None:
        await q.put(hit)
        await q.put(None)
        return

    cfg = resolve_llm(job.tier)   # modello/endpoint in base al piano del cliente
    models = cfg["models"]        # catena: [primario, riserva1, riserva2, ...]
    full = ""
    try:
        await _bucket.acquire()
        async for delta in ask_stream(job.question, job.context, model=models[0],
                                      base_url=cfg["base_url"], api_key=cfg["api_key"],
                                      timeout=LLM_PRIMARY_TIMEOUT, lang=job.lang):
            if delta:
                full += delta
                await q.put(delta)
        # Primo modello vuoto (rate-limit/errore): scorri la catena di riserva veloce (non-stream).
        if not full:
            for fb in models[1:]:
                log.warning("Stream vuoto, provo il modello di riserva %s", fb)
                await _bucket.acquire()
                ans = await ask(job.question, job.context, model=fb,
                                base_url=cfg["base_url"], api_key=cfg["api_key"], lang=job.lang)
                if ans:
                    full = ans
                    await q.put(ans)
                    break
        if full:
            _lru_put(job.key, full)
            await _db_put(job.key, job.question, full)
        else:
            await q.put(FALLBACK)
    except Exception:
        log.exception("Errore nel worker LLM (stream)")
        if not full:
            await q.put(FALLBACK)
    finally:
        await q.put(None)   # sentinel: fine stream


async def _worker():
    log.info("LLM worker avviato (LLM_RPM=%d, CACHE_MAX=%d)", LLM_RPM, CACHE_MAX)
    while True:
        job = await _queue.get()
        try:
            if job.stream_q is not None:        # job in streaming: gestione dedicata
                await _handle_stream_job(job)
                continue
            # un'altra richiesta identica potrebbe aver popolato la cache nel frattempo
            hit = _lru_get(job.key)
            if hit is not None:
                if job.future and not job.future.done():
                    job.future.set_result(hit)
                continue

            # Il free tier può restituire risposte vuote in modo transitorio:
            # ritenta qualche volta prima di mostrare il fallback all'utente.
            cfg = resolve_llm(job.tier)   # modello/endpoint in base al piano del cliente
            models = cfg["models"]        # catena: [primario, riserva1, riserva2, ...]
            answer = None
            for i, model in enumerate(models):
                # Sul PRIMO modello ritenta le risposte vuote transitorie; sugli altri
                # (usati perche' il primo e' in rate-limit) una sola prova, veloce.
                tries = (LLM_RETRIES + 1) if i == 0 else 1
                for attempt in range(tries):
                    await _bucket.acquire()
                    answer = await ask(job.question, job.context, model=model,
                                       base_url=cfg["base_url"], api_key=cfg["api_key"],
                                       timeout=LLM_PRIMARY_TIMEOUT, lang=job.lang)
                    if answer:
                        break
                    if attempt < tries - 1:
                        log.warning("Risposta vuota da %s (%d/%d), ritento", model, attempt + 1, tries)
                        await asyncio.sleep(LLM_RETRY_DELAY)
                if answer:
                    break
                if i + 1 < len(models):
                    log.warning("Modello %s non ha risposto, passo al successivo", model)

            if answer:
                _lru_put(job.key, answer)
                await _db_put(job.key, job.question, answer)
                result = answer
            else:
                result = FALLBACK  # non cacheare il fallback: riproverà la prossima volta

            if not job.future.done():
                job.future.set_result(result)
        except Exception:
            log.exception("Errore nel worker LLM")
            if not job.future.done():
                job.future.set_result(FALLBACK)
        finally:
            _queue.task_done()


def start_worker():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_worker())
    return _task


def stop_worker():
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None
