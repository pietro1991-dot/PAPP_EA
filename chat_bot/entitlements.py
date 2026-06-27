"""Entitlements: COSA sblocca ogni piano. Fonte unica di verità per tutto il prodotto.

Modello (tutto in abbonamento):
  - Starter : solo SEGNALI (notifiche; il cliente esegue a mano). Chatbot tier free.
  - Pro     : SEGNALI + EA (licenza, auto). Chatbot tier paid.
  - Elite   : SEGNALI + EA + chatbot premium (LLM migliore).
  - (nessun piano / non loggato) : demo → chatbot free, niente segnali, niente EA.

Usato da:
  - /api/ea/validate  -> can_ea(plan): solo pro/elite possono far girare l'EA.
  - feed/push segnali -> can_signals(plan): starter+.
  - chatbot           -> chatbot_tier(plan): free|paid|premium (modello LLM).
"""

PLAN_FEATURES = {
    "starter": {"signals": True,  "ea": False, "chatbot": "free"},
    "pro":     {"signals": True,  "ea": True,  "chatbot": "paid"},
    "elite":   {"signals": True,  "ea": True,  "chatbot": "premium"},
}

# Default per chi non ha un piano valido (demo): chatbot free, niente segnali/EA.
DEFAULT = {"signals": False, "ea": False, "chatbot": "free"}


def features(plan: str | None) -> dict:
    """Ritorna il dict di feature per il piano (case-insensitive)."""
    return PLAN_FEATURES.get((plan or "").strip().lower(), DEFAULT)


def can_signals(plan: str | None) -> bool:
    return features(plan)["signals"]


def can_ea(plan: str | None) -> bool:
    return features(plan)["ea"]


def chatbot_tier(plan: str | None) -> str:
    return features(plan)["chatbot"]
