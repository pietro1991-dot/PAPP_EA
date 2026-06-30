"""Entitlements: COSA sblocca ogni piano. Fonte unica di verità per tutto il prodotto.

Il campo `plan` della licenza è una lista di SKU separati da virgola (così un
utente può possedere più cose, p.es. "single:EURUSD,single:GBPUSD"). SKU validi:
  - signals / starter      : solo SEGNALI (esecuzione manuale). Chatbot free.
  - single:<SIMBOLO>       : 1 EA automatico (es. single:EURUSD). Chatbot paid.
  - pack_base / pack_rev   : tutti gli EA di un motore. Chatbot paid.
  - pro (legacy)           : = pack_base (tutti gli EA del Motore Base). Chatbot paid.
  - portfolio / elite      : tutti i motori + tutti gli EA. Chatbot premium.
  - (nessuno / non loggato) : demo -> chatbot free, niente segnali/EA.

Quali EA (simboli) sblocca ciascuno SKU è definito nel catalogo (catalog.py).

Usato da:
  - /api/ea/validate  -> can_ea_symbol(plan, symbol): l'EA gira solo sui simboli posseduti.
  - feed/push segnali -> can_signals(plan): chi ha un piano valido.
  - chatbot           -> chatbot_tier(plan): free|paid|premium (modello LLM).
  - showroom/checkout -> owned_eas(plan): quali EA sono attivi vs da sbloccare.
"""
import catalog

# Tier chatbot per ogni "tipo" di SKU; per un piano multi-SKU si prende il massimo.
_TIER_RANK = {"free": 0, "paid": 1, "premium": 2}


def _sku_tier(sku: str) -> str:
    sku = (sku or "").strip().lower()
    if sku in ("portfolio", "elite"):
        return "premium"
    if sku in ("starter", "signals", ""):
        return "free"
    if sku == "pro" or sku.startswith("pack_") or sku.startswith("single:"):
        return "paid"
    return "free"


def _skus(plan: str | None):
    return [s.strip().lower() for s in (plan or "").split(",") if s.strip()]


def owned_eas(plan: str | None) -> set:
    """Set di id EA (simboli) posseduti dall'utente. Vuoto = nessun EA."""
    return catalog.owned_eas(plan or "")


def can_ea_symbol(plan: str | None, symbol: str) -> bool:
    """True se l'utente possiede l'EA su quel simbolo (gate per-EA)."""
    return (symbol or "").upper() in owned_eas(plan)


def can_ea(plan: str | None) -> bool:
    """True se l'utente possiede ALMENO un EA automatico."""
    return bool(owned_eas(plan))


def can_signals(plan: str | None) -> bool:
    """I segnali sono inclusi in qualsiasi SKU riconosciuto (anche solo Signals)."""
    skus = _skus(plan)
    return any(
        s in ("signals", "starter", "pro", "elite", "portfolio")
        or s.startswith("pack_") or s.startswith("single:")
        for s in skus
    )


def chatbot_tier(plan: str | None) -> str:
    """Tier LLM = il massimo tra gli SKU posseduti (free<paid<premium)."""
    best = "free"
    for s in _skus(plan):
        if _TIER_RANK[_sku_tier(s)] > _TIER_RANK[best]:
            best = _sku_tier(s)
    return best


def features(plan: str | None) -> dict:
    """Riepilogo entitlement (per /api/me e per la UI)."""
    eas = sorted(owned_eas(plan))
    return {
        "signals": can_signals(plan),
        "ea": bool(eas),
        "eas": eas,                       # quali simboli sono attivi
        "chatbot": chatbot_tier(plan),
    }
