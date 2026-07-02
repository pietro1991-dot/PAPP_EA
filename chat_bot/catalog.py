"""Catalogo prodotti PHAI: i singoli EA (con l'EROE in evidenza) e i PACCHETTI-portafoglio.

Fonte unica di verità per:
  - lo showroom "Strategie" (i 5 EA singoli + i 3 pacchetti);
  - i veicoli d'acquisto (singolo EA / pacchetto);
  - gli entitlement (quali EA/simboli possiede un utente, in base agli SKU del piano).

Modello commerciale (micro-abbonamento di volume):
  Prezzi BASSI per acquisire tanti utenti; EUR/USD (il cavallo di battaglia) in
  evidenza come esca; upsell ai pacchetti-portafoglio che si vendono sulla STABILITÀ
  (drawdown basso grazie alla diversificazione). Assistente AI come add-on.

  Singolo 4€ -> Difensivo 7€ -> Bilanciato 9€ -> Completo 12€ ; + Assistente 5€.

NB: la vecchia navigazione "per Motore" è stata TOLTA dal prodotto. Il tipo di
strategia (trend / reversione) resta solo come ETICHETTA descrittiva su ogni EA e
come SPIEGAZIONE del perché i pacchetti funzionano (strategie decorrelate = DD basso).

I prezzi qui sono il DEFAULT: sovrascrivibili con env PRICE_* senza toccare il codice.
Le statistiche live (win rate, PnL, grafico) arrivano dai backtest, non da qui.
"""
import os


def _price(key: str, default: float) -> float:
    try:
        return float(os.getenv(f"PRICE_{key.upper()}", "") or default)
    except ValueError:
        return default


# --- Tipo di strategia (ex "motori"): ora solo ETICHETTA descrittiva -------
ENGINES = {
    "base": {
        "key": "base",
        "name": {"it": "Trend · linee-prezzo", "en": "Trend · price-lines"},
        "tagline": {"it": "Segue la struttura del prezzo di un singolo strumento"},
        "color": "#5b9dff",
    },
    "rev": {
        "key": "rev",
        "name": {"it": "Reversione", "en": "Reversion"},
        "tagline": {"it": "Compra la paura, vende l'euforia sui cross correlati"},
        "color": "#c9a14a",
    },
}

# --- I singoli EA (id = simbolo). flagship=True -> il cavallo di battaglia ---
EAS = [
    {
        "id": "EURUSD", "engine": "base", "symbol": "EURUSD", "live": True, "flagship": True,
        "name": "PHAI EUR/USD",
        "tagline": {"it": "Il nostro best-seller: la struttura del prezzo su EUR/USD."},
        "mechanism": {"it": "Legge le 8 linee/medie sul grafico giornaliero (D1) e opera i "
                            "crossover validati out-of-sample (pattern P1–P6). Take-profit stretto, "
                            "stop dinamico ancorato alle medie. Pochissimi trade, win rate altissimo."},
        "risk": {"it": "Il più solido del parco: rendimento storico altissimo, drawdown ~20%."},
    },
    {
        "id": "GBPUSD", "engine": "base", "symbol": "GBPUSD", "live": True, "flagship": False,
        "name": "PHAI GBP/USD",
        "tagline": {"it": "Cavalca le gambe direzionali della sterlina."},
        "mechanism": {"it": "Tre pattern trend-following sulle linee del D1: entra nella direzione "
                            "del movimento e lascia correre. Anti-correlato a EUR/USD (copertura)."},
        "risk": {"it": "Aggressivo: drawdown elevato da solo. Rende al meglio dentro un pacchetto."},
    },
    {
        "id": "USDCHF", "engine": "base", "symbol": "USDCHF", "live": True, "flagship": False,
        "name": "PHAI USD/CHF",
        "tagline": {"it": "Struttura del prezzo sul franco svizzero."},
        "mechanism": {"it": "Pattern P1+P7 sul D1, con esposizione controllata. Edge sottile ma "
                            "decorrelato dagli altri: utile come diversificatore in un pacchetto."},
        "risk": {"it": "Sensibile: pensato per size contenute e diversificazione."},
    },
    {
        "id": "EURGBP", "engine": "rev", "symbol": "EURGBP", "live": True, "flagship": False,
        "name": "PHAI EUR/GBP",
        "tagline": {"it": "Valore relativo EUR/GBP: compra la paura, vende l'euforia."},
        "mechanism": {"it": "Misura quanto il cross EUR/GBP è 'tirato' (percentile della distanza "
                            "dalla media) e fa fade verso la media. Vol-targeting che riduce la size "
                            "in alta volatilità. Completamente decorrelato dagli EA trend."},
        "risk": {"it": "Reversione pura: backtest +110% in 16 anni, win ~79%, drawdown ~21%."},
    },
    {
        "id": "GBPCHF", "engine": "rev", "symbol": "GBPCHF", "live": True, "flagship": False,
        "name": "PHAI GBP/CHF",
        "tagline": {"it": "Valore relativo GBP/CHF: la reversione a orizzonte mensile."},
        "mechanism": {"it": "Come EUR/GBP ma sul cross GBP/CHF: misura quanto è 'tirato' e fa fade "
                            "verso la media. Edge raro (~8 trade l'anno) e decorrelato da EUR/GBP."},
        "risk": {"it": "Alto rendimento (+258% in 16 anni) e alto drawdown da solo (~54%): "
                       "in un pacchetto, a size ridotta, il suo DD si schiaccia."},
    },
]

EA_BY_ID = {e["id"]: e for e in EAS}
ALL_EA_IDS = [e["id"] for e in EAS]
LIVE_EA_IDS = [e["id"] for e in EAS if e["live"]]
FLAGSHIP_ID = next((e["id"] for e in EAS if e.get("flagship")), "EURUSD")


def eas_of_engine(engine_key: str):
    return [e["id"] for e in EAS if e["engine"] == engine_key]


# --- I PACCHETTI-portafoglio (i veicoli d'acquisto che si vendono sul DD basso) ---
# Ogni pacchetto = una composizione misurata (vedi PORTAFOGLI_EA.md + cartelle
# Portafoglio_*_*EA). Si vendono sulla STABILITÀ (drawdown), non sul rendimento.
PACKS = [
    {
        "id": "pack_difensivo", "kind": "pack",
        "name": {"it": "Pacchetto Difensivo", "en": "Defensive Pack"},
        "tagline": {"it": "2 EA (EUR/USD + EUR/GBP): l'ingresso più semplice e tranquillo. DD ~12%."},
        "eas": ["EURUSD", "EURGBP"],
        "stats": {"cagr": 10.0, "dd": 12.5},
        "price": _price("PACK_DIFENSIVO", 7),
        "recommended": False,
    },
    {
        "id": "pack_bilanciato", "kind": "pack",
        "name": {"it": "Pacchetto Bilanciato", "en": "Balanced Pack"},
        "tagline": {"it": "3 EA (EUR/USD + EUR/GBP + GBP/CHF): il migliore equilibrio. DD ~11.5%."},
        "eas": ["EURUSD", "EURGBP", "GBPCHF"],
        "stats": {"cagr": 10.2, "dd": 11.5},
        "price": _price("PACK_BILANCIATO", 9),
        "recommended": True,
    },
    {
        "id": "pack_completo", "kind": "pack",
        "name": {"it": "Pacchetto Completo", "en": "Complete Pack"},
        "tagline": {"it": "Tutti e 5 gli EA in risk-parity: la curva più stabile. DD ~10%. Best value."},
        "eas": list(ALL_EA_IDS),
        "stats": {"cagr": 11.9, "dd": 10.3},
        "price": _price("PACK_COMPLETO", 12),
        "recommended": False,
    },
]
PACK_BY_ID = {p["id"]: p for p in PACKS}

# PORTFOLIO = alias del pacchetto Completo (retrocompatibilità con app.py e licenze).
PORTFOLIO = {
    "id": "portfolio", "kind": "portfolio",
    "name": {"it": "Pacchetto Completo", "en": "Complete Pack"},
    "tagline": {"it": "Tutti e 5 gli EA, AI premium e i nuovi EA inclusi appena escono."},
    "eas": list(ALL_EA_IDS),
    "price": _price("PACK_COMPLETO", 12),
}

SINGLE_PRICE = _price("SINGLE_EA", 4)      # prezzo di un singolo EA (esca, molto basso)
SIGNALS_PRICE = _price("ASSISTANT", 5)     # piano Assistente + Segnali (SKU "signals")

# --- Piano ASSISTENTE + SEGNALI (senza EA): l'ingresso a più bassa frizione ---
# Non serve MT5 né broker: ricevi i SEGNALI via PUSH e l'ASSISTENTE AI ti guida.
# È il prodotto d'ingresso per chi non vuole (ancora) automatizzare.
ASSISTANT = {
    "id": "signals", "kind": "assistant",
    "name": {"it": "Assistente + Segnali", "en": "Assistant + Signals"},
    "tagline": {"it": "Zero installazioni: i segnali ti arrivano con una notifica push e "
                      "l'assistente AI ti dice cosa fare, quando e perché. Poi, quando vuoi, "
                      "automatizzi con un EA."},
    "features": {"it": ["🔔 Segnali in tempo reale via notifica push",
                        "🤖 Assistente AI dedicato (senza limiti giornalieri)",
                        "📊 Tutti i backtest e lo stato del mercato in chiaro"]},
    "price": SIGNALS_PRICE,
}


# --- Risoluzione SKU -> EA posseduti --------------------------------------
# Il campo `plan` della licenza è una lista di SKU separati da virgola, p.es.
# "single:EURUSD,single:GBPUSD" oppure "pack_bilanciato" oppure "portfolio".
# Legacy supportati: starter/pro/elite/signals + pack_base/pack_rev.
def _pack_eas(pack_id: str):
    p = PACK_BY_ID.get(pack_id)
    return list(p["eas"]) if p else []


def sku_eas(sku: str):
    """EA (simboli) sbloccati da un singolo SKU. Ritorna lista di id EA."""
    sku = (sku or "").strip().lower()
    if not sku:
        return []
    if sku in ("portfolio", "elite", "pack_completo"):
        return list(ALL_EA_IDS)
    if sku == "pro":                       # legacy: Pro = tutti gli EA "trend"
        return eas_of_engine("base")
    if sku in ("starter", "signals"):      # solo assistente/segnali, nessun EA
        return []
    if sku == "pack_base":                 # legacy engine-pack
        return eas_of_engine("base")
    if sku == "pack_rev":                  # legacy engine-pack
        return eas_of_engine("rev")
    if sku.startswith("pack_"):
        return _pack_eas(sku)
    if sku.startswith("single:"):
        eid = sku.split(":", 1)[1].upper()
        return [eid] if eid in EA_BY_ID else []
    return []


def owned_eas(plan: str):
    """Unione degli EA posseduti da tutti gli SKU del piano. Set di id EA."""
    owned = set()
    for sku in (plan or "").split(","):
        owned.update(sku_eas(sku))
    return owned


def offer_for_ea(ea_id: str):
    """Le 3 opzioni d'acquisto mostrate quando un EA è bloccato:
    singolo -> Pacchetto Bilanciato (consigliato) -> Pacchetto Completo (best value)."""
    e = EA_BY_ID.get(ea_id)
    if not e:
        return []
    bil = PACK_BY_ID.get("pack_bilanciato")
    com = PACK_BY_ID.get("pack_completo")
    out = [{
        "sku": f"single:{ea_id}", "kind": "single", "title": f"Solo {e['name']}",
        "price": SINGLE_PRICE, "eas": [ea_id], "recommended": False,
    }]
    if bil:
        out.append({
            "sku": bil["id"], "kind": "pack", "title": bil["name"]["it"],
            "price": bil["price"], "eas": list(bil["eas"]), "recommended": True,
        })
    if com:
        out.append({
            "sku": com["id"], "kind": "pack", "title": com["name"]["it"],
            "price": com["price"], "eas": list(com["eas"]), "best_value": True,
        })
    return out


def is_valid_sku(sku: str) -> bool:
    sku = (sku or "").strip().lower()
    if sku in ("portfolio", "elite", "pro", "signals", "starter", "pack_base", "pack_rev"):
        return True
    if sku.startswith("pack_"):
        return sku in PACK_BY_ID
    if sku.startswith("single:"):
        return sku.split(":", 1)[1].upper() in EA_BY_ID
    return False


def sku_label_price(sku: str, lang: str = "it"):
    """(etichetta, prezzo) di uno SKU, per il checkout."""
    sku = (sku or "").strip().lower()
    if sku in ("portfolio", "elite", "pack_completo"):
        return (tr(PORTFOLIO["name"], lang), PORTFOLIO["price"])
    if sku in ("signals", "starter"):
        return (tr(ASSISTANT["name"], lang), SIGNALS_PRICE)
    if sku in ("pro", "pack_base"):
        p = PACK_BY_ID.get("pack_completo")
        return ("PHAI Autopilot", p["price"] if p else 12)
    if sku.startswith("pack_"):
        p = PACK_BY_ID.get(sku)
        if p:
            return (tr(p["name"], lang), p["price"])
    if sku.startswith("single:"):
        e = EA_BY_ID.get(sku.split(":", 1)[1].upper())
        if e:
            return (f"Solo {e['name']}", SINGLE_PRICE)
    return ("PHAI", PORTFOLIO["price"])


def tr(field, lang: str = "it"):
    """Helper i18n con fallback all'IT per i campi multilingua del catalogo."""
    if not isinstance(field, dict):
        return field
    return field.get(lang) or field.get("it") or next(iter(field.values()), "")
