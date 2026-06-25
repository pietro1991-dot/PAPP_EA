import os
import json
import logging
from typing import Optional

import httpx

log = logging.getLogger("papp.llm")

# OpenCode Zen è OpenAI-compatibile: chiamata HTTP diretta, niente processo opencode.
ZEN_BASE_URL = os.getenv("ZEN_BASE_URL", "https://opencode.ai/zen/v1")
ZEN_MODEL = os.getenv("ZEN_MODEL", "deepseek-v4-flash-free")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
# deepseek-v4-flash-free è un modello "reasoning": consuma token nel ragionamento
# prima di produrre `content`. Serve un tetto ampio o `content` resta vuoto.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))
# deepseek accetta reasoning_effort=low (riduce un po' il ragionamento, chat più veloce).
# Vuoto = ometti il parametro (per modelli che lo rifiutano con 400).
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low").strip()

SYSTEM_PROMPT = (
    "Sei un assistente esperto di trading algoritmico su MetaTrader 5. "
    "Rispondi in italiano in modo chiaro e conciso. "
    "Usa i dati forniti di pattern, segnali e performance per rispondere. "
    "Se non hai dati sufficienti, dillo onestamente. "
    "Risposte brevi, massimo 3 paragrafi."
)


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


async def ask(question: str, context: Optional[str] = None) -> Optional[str]:
    """Interroga l'LLM via API HTTP OpenAI-compatibile (OpenCode Zen).
    Ritorna il testo, oppure None su errore (il worker decide il fallback)."""
    key = _api_key()
    if not key:
        log.error("OPENCODE_API_KEY mancante: impossibile interrogare l'LLM")
        return None

    payload = {
        "model": ZEN_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(question, context)},
        ],
        "max_tokens": LLM_MAX_TOKENS,
    }
    if LLM_REASONING_EFFORT:
        payload["reasoning_effort"] = LLM_REASONING_EFFORT
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            r = await client.post(
                f"{ZEN_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        if r.status_code != 200:
            log.warning("Zen API HTTP %s: %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        content = (data["choices"][0]["message"].get("content") or "").strip()
        return content or None
    except Exception:
        log.exception("Errore nella chiamata all'API Zen")
        return None
