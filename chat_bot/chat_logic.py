import os
import re
import json
import logging
from typing import Optional

import httpx

log = logging.getLogger("papp.llm")

# I modelli gratuiti (mimo/deepseek, di sviluppo cinese) ogni tanto "perdono" un
# carattere CJK al posto della parola. Le nostre lingue (it/en/fr/es) sono tutte in
# alfabeto latino: rimuoviamo i caratteri cinesi/giapponesi/coreani e fullwidth.
_CJK_RE = re.compile(
    "[　-〿぀-ヿㇰ-ㇿ㐀-䶿一-鿿"
    "豈-﫿＀-￯가-힯]"
)


def _strip_cjk(text: str) -> str:
    if not text or not _CJK_RE.search(text):
        return text
    # rimuove i CJK e compatta gli spazi doppi che potrebbero restare
    return re.sub(r"  +", " ", _CJK_RE.sub("", text))

# OpenCode Zen è OpenAI-compatibile: chiamata HTTP diretta, niente processo opencode.
ZEN_BASE_URL = os.getenv("ZEN_BASE_URL", "https://opencode.ai/zen/v1")
ZEN_MODEL = os.getenv("ZEN_MODEL", "mimo-v2.5-free")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
# deepseek-v4-flash-free è un modello "reasoning": consuma token nel ragionamento
# prima di produrre `content`. Serve un tetto ampio o `content` resta vuoto.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3000"))
# deepseek accetta reasoning_effort=low (riduce un po' il ragionamento, chat più veloce).
# Vuoto = ometti il parametro (per modelli che lo rifiutano con 400).
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low").strip()

# --- Modello LLM per TIER (free / paid / premium) -----------------------------
# Default: TUTTO sul free (Zen) finché non imposti i modelli a pagamento. Così la
# capacità di differenziare per piano è già pronta, ma resti a costo zero fino alla
# vendita. Per attivare Claude sui paganti: imposta LLM_PAID_MODEL (e, se non passa
# da Zen, LLM_PAID_BASE_URL + LLM_PAID_API_KEY). LLM_PREMIUM_MODEL = Elite.
LLM_FREE_MODEL = os.getenv("LLM_FREE_MODEL", ZEN_MODEL)
LLM_FREE_FALLBACK = os.getenv("LLM_FREE_FALLBACK", "deepseek-v4-flash-free").strip()
LLM_PAID_MODEL = os.getenv("LLM_PAID_MODEL", "").strip()        # es. un modello Claude (Pro)
LLM_PREMIUM_MODEL = os.getenv("LLM_PREMIUM_MODEL", "").strip()  # es. Claude più capace (Elite)
LLM_PAID_BASE_URL = os.getenv("LLM_PAID_BASE_URL", "").strip()  # vuoto = stesso endpoint del free (Zen)
LLM_PAID_API_KEY = os.getenv("LLM_PAID_API_KEY", "").strip()    # vuoto = stessa chiave del free


def resolve_llm(tier: str = "free") -> dict:
    """Config LLM per tier: {base_url, api_key, model, fallback}.
    tier: 'free' (Demo/Starter) · 'paid' (Pro) · 'premium' (Elite).
    Se i modelli a pagamento non sono impostati, ricade sul free (zero rework)."""
    free = {"base_url": ZEN_BASE_URL, "api_key": _api_key(), "model": LLM_FREE_MODEL, "fallback": LLM_FREE_FALLBACK}
    paid_base = LLM_PAID_BASE_URL or ZEN_BASE_URL
    paid_key = LLM_PAID_API_KEY or _api_key()
    if tier == "premium" and LLM_PREMIUM_MODEL:
        return {"base_url": paid_base, "api_key": paid_key, "model": LLM_PREMIUM_MODEL, "fallback": LLM_PAID_MODEL or LLM_FREE_MODEL}
    if tier in ("paid", "premium") and LLM_PAID_MODEL:
        return {"base_url": paid_base, "api_key": paid_key, "model": LLM_PAID_MODEL, "fallback": LLM_FREE_MODEL}
    return free


LANG_NAMES = {
    "it": "italiano",
    "en": "English",
    "fr": "français",
    "es": "español",
}

SYSTEM_PROMPT = (
    "Sei l'assistente del PAPP_EA, un Expert Advisor di trading su MetaTrader 5. "
    "Rispondi in modo chiaro e ben strutturato (usa elenchi puntati e "
    "tabelle quando rendono la risposta più leggibile). "
    "USA ESCLUSIVAMENTE i dati forniti nel contesto (stato conto, performance per simbolo e "
    "per pattern, periodo, ultimi segnali) e la conoscenza sull'EA qui sotto: ogni numero che "
    "fornisci deve provenire da lì, non inventarlo MAI. Se un dato non è presente nel contesto, "
    "dillo chiaramente invece di stimarlo. "
    "Capisci sempre l'intento dell'utente: se la richiesta è ambigua o mancano informazioni per "
    "rispondere bene, fai prima una breve domanda di chiarimento. "
    "Completa sempre la risposta, senza troncarla a metà. Sii conciso ma esaustivo."
)

# Base di conoscenza sull'EA, iniettata nel system prompt (modificabile senza toccare il codice).
_KNOWLEDGE_FILE = os.getenv(
    "EA_KNOWLEDGE_FILE", os.path.join(os.path.dirname(__file__), "ea_knowledge.md")
)


def _load_knowledge() -> str:
    try:
        with open(_KNOWLEDGE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


EA_KNOWLEDGE = _load_knowledge()


def _system_content(lang: str = "it") -> str:
    langname = LANG_NAMES.get(lang, LANG_NAMES["it"])
    directive = (
        f"IMPORTANTE: rispondi SEMPRE e SOLO in {langname}, qualunque sia la lingua "
        f"dei dati o del contesto qui sotto (che possono essere in italiano). "
        f"Scrivi ESCLUSIVAMENTE con l'alfabeto latino: non usare MAI caratteri cinesi, "
        f"giapponesi, coreani o altri simboli non latini.\n\n"
    )
    body = SYSTEM_PROMPT
    if EA_KNOWLEDGE:
        body += "\n\n--- Conoscenza sul PAPP_EA ---\n" + EA_KNOWLEDGE
    return directive + body


def _api_key() -> Optional[str]:
    """API key Zen: da env OPENCODE_API_KEY, con fallback al file auth.json di opencode."""
    key = os.getenv("OPENCODE_API_KEY")
    if key:
        return key
    try:
        path = os.path.expanduser("~/.local/share/opencode/auth.json")
        with open(path) as f:
            return json.load(f)["opencode"]["key"]
    except Exception:
        return None


def build_user_message(question: str, context: Optional[str] = None) -> str:
    msg = ""
    if context:
        msg += f"Contesto:\n{context}\n\n"
    msg += f"Domanda: {question}"
    return msg


async def ask(
    question: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    lang: str = "it",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[str]:
    """Interroga l'LLM via API HTTP OpenAI-compatibile (OpenCode Zen o altro endpoint).
    `model`/`base_url`/`api_key` permettono di usare un provider diverso per tier
    (es. Claude a pagamento). `timeout` limita l'attesa.
    Ritorna il testo, oppure None su errore (il worker decide il fallback)."""
    key = api_key or _api_key()
    if not key:
        log.error("Chiave LLM mancante: impossibile interrogare l'LLM")
        return None

    model = model or LLM_FREE_MODEL
    base = base_url or ZEN_BASE_URL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_content(lang)},
            {"role": "user", "content": build_user_message(question, context)},
        ],
        "max_tokens": LLM_MAX_TOKENS,
    }
    # reasoning_effort solo per i modelli deepseek (altri lo rifiutano con 400).
    if LLM_REASONING_EFFORT and "deepseek" in model:
        payload["reasoning_effort"] = LLM_REASONING_EFFORT
    try:
        async with httpx.AsyncClient(timeout=timeout or LLM_TIMEOUT) as client:
            r = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        if r.status_code != 200:
            log.warning("LLM API HTTP %s: %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        content = _strip_cjk((data["choices"][0]["message"].get("content") or "").strip())
        return content or None
    except Exception:
        log.exception("Errore nella chiamata all'API LLM")
        return None


async def ask_stream(
    question: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    lang: str = "it",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Come ask() ma in streaming: yield i pezzi di testo (delta) man mano che arrivano.
    Su errore non produce nulla (il worker decide il fallback)."""
    key = api_key or _api_key()
    if not key:
        log.error("Chiave LLM mancante: impossibile interrogare l'LLM")
        return

    model = model or LLM_FREE_MODEL
    base = base_url or ZEN_BASE_URL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_content(lang)},
            {"role": "user", "content": build_user_message(question, context)},
        ],
        "max_tokens": LLM_MAX_TOKENS,
        "stream": True,
    }
    if LLM_REASONING_EFFORT and "deepseek" in model:
        payload["reasoning_effort"] = LLM_REASONING_EFFORT
    try:
        async with httpx.AsyncClient(timeout=timeout or LLM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            ) as r:
                if r.status_code != 200:
                    body = await r.aread()
                    log.warning("LLM API HTTP %s (stream): %s", r.status_code, body[:200])
                    return
                async for line in r.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                        delta = obj["choices"][0].get("delta", {}).get("content")
                        if delta:
                            delta = _strip_cjk(delta)
                            if delta:
                                yield delta
                    except Exception:
                        continue
    except Exception:
        log.exception("Errore nello streaming dall'API Zen")
        return
