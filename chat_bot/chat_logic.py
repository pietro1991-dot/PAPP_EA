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
# Catena di riserva: modelli VELOCI provati in ordine se il primo va in rate-limit/vuoto.
# Metti solo modelli rapidi (es. "*-flash-free"), separati da virgola.
LLM_FREE_FALLBACK = os.getenv("LLM_FREE_FALLBACK", "deepseek-v4-flash-free").strip()
LLM_FREE_FALLBACKS = os.getenv("LLM_FREE_FALLBACKS", LLM_FREE_FALLBACK).strip()


def _chain(*models) -> list:
    """Costruisce una catena ordinata di modelli, deduplicata, ignorando i vuoti.
    Ogni voce può essere una lista separata da virgole."""
    seen, out = set(), []
    for m in models:
        for part in (m or "").split(","):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                out.append(part)
    return out
LLM_PAID_MODEL = os.getenv("LLM_PAID_MODEL", "").strip()        # es. un modello Claude (Pro)
LLM_PREMIUM_MODEL = os.getenv("LLM_PREMIUM_MODEL", "").strip()  # es. Claude più capace (Elite)
LLM_PAID_BASE_URL = os.getenv("LLM_PAID_BASE_URL", "").strip()  # vuoto = stesso endpoint del free (Zen)
LLM_PAID_API_KEY = os.getenv("LLM_PAID_API_KEY", "").strip()    # vuoto = stessa chiave del free


def resolve_llm(tier: str = "free") -> dict:
    """Config LLM per tier: {base_url, api_key, model, fallback}.
    tier: 'free' (Demo/Starter) · 'paid' (Pro) · 'premium' (Elite).
    Se i modelli a pagamento non sono impostati, ricade sul free (zero rework)."""
    free_chain = _chain(LLM_FREE_MODEL, LLM_FREE_FALLBACKS)

    def _pack(base_url, api_key, chain):
        return {"base_url": base_url, "api_key": api_key, "models": chain,
                "model": chain[0], "fallback": (chain[1] if len(chain) > 1 else "")}

    free = _pack(ZEN_BASE_URL, _api_key(), free_chain)
    paid_base = LLM_PAID_BASE_URL or ZEN_BASE_URL
    paid_key = LLM_PAID_API_KEY or _api_key()
    if tier == "premium" and LLM_PREMIUM_MODEL:
        # premium -> free: sempre la catena veloce come rete di sicurezza finale
        return _pack(paid_base, paid_key, _chain(LLM_PREMIUM_MODEL, LLM_PAID_MODEL, *free_chain))
    if tier in ("paid", "premium") and LLM_PAID_MODEL:
        return _pack(paid_base, paid_key, _chain(LLM_PAID_MODEL, *free_chain))
    return free


LANG_NAMES = {
    "it": "italiano",
    "en": "English",
    "fr": "français",
    "es": "español",
}

SYSTEM_PROMPT = (
    "Sei l'assistente di PHAI, una piattaforma di trading algoritmico su MetaTrader 5: "
    "5 strategie (EA) singole, 3 pacchetti-portafoglio, i segnali in tempo reale e questo "
    "assistente. Aiuti gli utenti a: capire lo STATO ATTUALE del mercato e delle strategie "
    "('dove siamo', quanto siamo vicini a un segnale), leggere i SEGNALI (entrata/TP/SL, radar), "
    "analizzare la PERFORMANCE, e scegliere il PRODOTTO/abbonamento giusto (singolo, pacchetto, "
    "o piano Assistente+Segnali). "
    "Rispondi in modo chiaro e ben strutturato (elenchi puntati e tabelle quando aiutano). "
    "USA ESCLUSIVAMENTE i dati forniti nel contesto (stato conto, performance per simbolo e "
    "pattern, periodo, ultimi segnali, STATO STRATEGIE 'dove siamo ora') e la conoscenza qui "
    "sotto: ogni numero deve provenire da lì, non inventarlo MAI. Se un dato non è nel contesto, "
    "dillo chiaramente invece di stimarlo. "
    "REGOLA DI CONFORMITÀ (prodotto finanziario): i numeri sono BACKTEST storici (simulazioni), "
    "NON promesse di rendimento futuro. Non garantire MAI profitti, non dare consigli finanziari "
    "personalizzati come 'investi X'; ricorda che il trading comporta rischio di perdita. "
    "Capisci l'intento: se la richiesta è ambigua o mancano informazioni, fai prima una breve "
    "domanda di chiarimento. Completa sempre la risposta, senza troncarla. Conciso ma esaustivo."
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


def _split_sections(md: str):
    """Divide la conoscenza in sezioni per header (#/##/###). Ognuna resta autonoma."""
    if not md:
        return []
    out = []
    for p in re.split(r"\n(?=#{1,3} )", md):
        header = p.split("\n", 1)[0].strip("# ").strip()
        out.append((header, p))
    return out


_KB_SECTIONS = _split_sections(EA_KNOWLEDGE)
_SYMBOLS = ("eurusd", "gbpusd", "usdchf", "eurgbp", "gbpchf")


def _relevant_knowledge(question: str) -> str:
    """RAG leggero (sezioni + keyword multilingua): inietta SOLO le sezioni pertinenti
    alla domanda, per tagliare i token SENZA perdere fatti. Include sempre un CORE; se la
    domanda è ambigua/generica o il match è debole -> inietta TUTTA la conoscenza (mai
    peggio di adesso). NON tocca i dati LIVE del conto (arrivano a parte, nel contesto)."""
    if not _KB_SECTIONS:
        return EA_KNOWLEDGE
    q = (question or "").lower().replace("/", "")
    if len(q) < 4:
        return EA_KNOWLEDGE

    def find(*subs):
        return [b for h, b in _KB_SECTIONS if any(s in h.lower() for s in subs)]

    chosen = list(find("due motori"))   # core: sempre incluso
    strong = False
    if any(k in q for k in ("install", "scaric", "avvi", "configur", "instalar", "installer")):
        chosen += find("installare"); strong = True
    if any(k in q for k in ("prezzo", "costa", "abbonam", "pacchett", "piano", "price", "cost", "precio", "prix", "paquet", "plan")):
        chosen += find("pacchetti", "prezzi", "consigliare", "strategie singole", "assistente"); strong = True
    syms = [s for s in _SYMBOLS if s in q]
    if syms and any(k in q for k in ("backtest", "reso", "rend", "drawdown", "risultat", "performance", "anno", "result", "return", "year")):
        chosen += find(*syms); strong = True
    if any(k in q for k in ("revers", "cross", "valore relativo", "oscillat", "relative value")):
        chosen += find("reversione", "basket"); strong = True
    if any(k in q for k in ("pattern", "linee", "media", "trend", "moving average")):
        chosen += find("motore base", "come funziona"); strong = True
    if not strong:   # nessun tema forte -> keyword generico (top 3 sezioni)
        scored = sorted(
            ((sum(1 for w in set(re.findall(r"[a-zà-ù]{4,}", q)) if w in b.lower()), b)
             for h, b in _KB_SECTIONS), key=lambda x: x[0], reverse=True)
        chosen += [b for s, b in scored[:3] if s > 0]

    seen = set()
    picked = [c for c in chosen if not (c in seen or seen.add(c))]
    joined = "\n\n".join(picked)
    if len(joined) < 400:   # match debole -> sicurezza: tutta la conoscenza
        return EA_KNOWLEDGE
    return joined


def _system_content(lang: str = "it", question: str = "") -> str:
    langname = LANG_NAMES.get(lang, LANG_NAMES["it"])
    directive = (
        f"IMPORTANTE: rispondi SEMPRE e SOLO in {langname}, qualunque sia la lingua "
        f"dei dati o del contesto qui sotto (che possono essere in italiano). "
        f"Scrivi ESCLUSIVAMENTE con l'alfabeto latino: non usare MAI caratteri cinesi, "
        f"giapponesi, coreani o altri simboli non latini.\n\n"
    )
    body = SYSTEM_PROMPT
    kb = _relevant_knowledge(question) if question else EA_KNOWLEDGE
    if kb:
        body += "\n\n--- Conoscenza su PHAI ---\n" + kb
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
            {"role": "system", "content": _system_content(lang, question)},
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
            {"role": "system", "content": _system_content(lang, question)},
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


async def translate(text: str, target_lang: str) -> Optional[str]:
    """Traduce copy marketing nella lingua target, preservando i segnaposto
    ([Nome], {{...}}) e la formattazione. Usato per generare le email multilingua."""
    cfg = resolve_llm("free")
    key = cfg["api_key"]
    if not key:
        return None
    langname = LANG_NAMES.get(target_lang, target_lang)
    sysmsg = (
        f"Sei un traduttore professionista di copy marketing. Traduci il testo in {langname} "
        "mantenendo tono persuasivo, naturale e scorrevole. REGOLE FERREE: non tradurre né "
        "modificare i segnaposto tra doppie graffe come {{demo}}, {{sblocca}}, {{app}}, "
        "{{license_key}}, {{unsubscribe}} e non toccare [Nome]: lasciali identici. Mantieni "
        "la stessa formattazione, gli a-capo e i marcatori [SUBJECT]/[BODY] se presenti. "
        "Rispondi SOLO con la traduzione, senza commenti."
    )
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": text}],
        "max_tokens": LLM_MAX_TOKENS,
    }
    if LLM_REASONING_EFFORT and "deepseek" in cfg["model"]:
        payload["reasoning_effort"] = LLM_REASONING_EFFORT
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            r = await client.post(f"{cfg['base_url']}/chat/completions",
                                  headers={"Authorization": f"Bearer {key}"}, json=payload)
        if r.status_code != 200:
            log.warning("translate HTTP %s: %s", r.status_code, r.text[:160])
            return None
        return _strip_cjk((r.json()["choices"][0]["message"].get("content") or "").strip()) or None
    except Exception:
        log.exception("translate fallita")
        return None
