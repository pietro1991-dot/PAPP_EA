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
from chat_logic import ask

log = logging.getLogger("papp.llm")

LLM_RPM = int(os.getenv("LLM_RPM", "15"))         # chiamate/minuto verso l'LLM (globale)
LLM_USER_RPM = int(os.getenv("LLM_USER_RPM", "5"))  # domande/minuto per utente
CACHE_MAX = int(os.getenv("CACHE_MAX", "500"))    # voci LRU in memoria
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "2"))     # tentativi extra su risposta vuota
LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", "2"))  # attesa tra i tentativi (s)

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
    future: asyncio.Future


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
    question: str, context: str, context_sig: str | None, user_id: int | None = None
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
        await _queue.put(_Job(question=question, context=context, key=key, future=fut))
        return await fut
    finally:
        if user_id is not None:
            _user_inflight.discard(user_id)


async def _worker():
    log.info("LLM worker avviato (LLM_RPM=%d, CACHE_MAX=%d)", LLM_RPM, CACHE_MAX)
    while True:
        job = await _queue.get()
        try:
            # un'altra richiesta identica potrebbe aver popolato la cache nel frattempo
            hit = _lru_get(job.key)
            if hit is not None:
                if not job.future.done():
                    job.future.set_result(hit)
                continue

            # Il free tier può restituire risposte vuote in modo transitorio:
            # ritenta qualche volta prima di mostrare il fallback all'utente.
            answer = None
            for attempt in range(LLM_RETRIES + 1):
                await _bucket.acquire()
                answer = await ask(job.question, job.context)
                if answer:
                    break
                if attempt < LLM_RETRIES:
                    log.warning(
                        "Risposta LLM vuota (tentativo %d/%d), ritento",
                        attempt + 1, LLM_RETRIES + 1,
                    )
                    await asyncio.sleep(LLM_RETRY_DELAY)

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
