"""Catalogo prodotti PHAI: i due MOTORI, i singoli EA, i PACCHETTI e il PORTFOLIO.

Fonte unica di verità per:
  - lo showroom "Strategie" (navigazione Motore -> EA, grafico + spiegazione);
  - i veicoli d'acquisto (singolo EA / pacchetto-motore / portfolio);
  - gli entitlement (quali EA/simboli possiede un utente, in base agli SKU del piano).

Modello commerciale (scala di valore, stile Sabri Suby):
  Demo (gratis) -> Signals (manuale) -> EA singolo (tripwire) ->
  Pacchetto-motore -> Portfolio completo (eroe) ; annuale = 2 mesi gratis.

I prezzi qui sono il DEFAULT di listino: si possono sovrascrivere con le env
PRICE_* senza toccare il codice. Le statistiche (win rate, PnL, grafico) NON
stanno qui: arrivano live dai backtest (/api/backtest/overview?symbol=...).
Le descrizioni sono in IT (mercato di lancio); EN/FR/ES sono un pass successivo
con fallback automatico all'IT.
"""
import os


def _price(key: str, default: float) -> float:
    try:
        return float(os.getenv(f"PRICE_{key.upper()}", "") or default)
    except ValueError:
        return default


# --- I due motori ---------------------------------------------------------
ENGINES = {
    "base": {
        "key": "base",
        "name": {"it": "Motore Base", "en": "Base Engine", "fr": "Moteur Base", "es": "Motor Base"},
        "tagline": {"it": "Linee-prezzo · struttura del prezzo di un singolo strumento"},
        "color": "#5b9dff",
    },
    "rev": {
        "key": "rev",
        "name": {"it": "Motore Reversione", "en": "Reversion Engine", "fr": "Moteur Réversion", "es": "Motor Reversión"},
        "tagline": {"it": "Valore relativo tra valute correlate · mean-reversion sui cross"},
        "color": "#c9a14a",
    },
}

# --- I singoli EA (id = simbolo) ------------------------------------------
# live=False -> "in arrivo" (vetrina ma non attivabile finché non è validato).
EAS = [
    {
        "id": "EURUSD", "engine": "base", "symbol": "EURUSD", "live": True,
        "name": "PHAI EUR/USD",
        "tagline": {"it": "Il cuore del parco: la struttura del prezzo su EUR/USD."},
        "mechanism": {"it": "Legge le 8 linee/medie sul grafico giornaliero (D1) e opera i "
                            "crossover validati out-of-sample (pattern P1–P6). Take-profit stretto, "
                            "stop dinamico ancorato alle medie. Pochissimi trade, win rate altissimo."},
        "risk": {"it": "Profilo conservativo: è il più solido del parco (drawdown storico ~20%)."},
    },
    {
        "id": "GBPUSD", "engine": "base", "symbol": "GBPUSD", "live": True,
        "name": "PHAI GBP/USD",
        "tagline": {"it": "Cavalca le gambe direzionali della sterlina."},
        "mechanism": {"it": "Tre pattern trend-following sulle linee del D1: entra nella direzione "
                            "del movimento e lascia correre. Profilo opposto e complementare a EUR/USD."},
        "risk": {"it": "Più aggressivo: rendimento alto ma drawdown elevato. Calibra la size."},
    },
    {
        "id": "USDCHF", "engine": "base", "symbol": "USDCHF", "live": True,
        "name": "PHAI USD/CHF",
        "tagline": {"it": "Struttura del prezzo sul franco svizzero."},
        "mechanism": {"it": "Pattern P1+P7 sul D1, con esposizione controllata (niente impilamento "
                            "illimitato delle posizioni). Edge sottile ma decorrelato dagli altri."},
        "risk": {"it": "Sensibile: pensato per size contenute e diversificazione."},
    },
    {
        "id": "EURGBP", "engine": "rev", "symbol": "EURGBP", "live": False,
        "name": "PHAI EUR/GBP",
        "tagline": {"it": "Valore relativo EUR/GBP: compra la paura, vende l'euforia."},
        "mechanism": {"it": "Non usa le linee. Misura quanto il cross EUR/GBP è 'tirato' (percentile "
                            "della distanza dalla media a 6 ore) e fa fade verso la media. Vol-targeting "
                            "che rimpicciolisce la size quando la volatilità sale, per tagliare gli anni-disastro."},
        "risk": {"it": "Reversione pura: win ~64%, drawdown ~30%, completamente decorrelato dal Motore Base."},
    },
]

EA_BY_ID = {e["id"]: e for e in EAS}
ALL_EA_IDS = [e["id"] for e in EAS]
LIVE_EA_IDS = [e["id"] for e in EAS if e["live"]]


def eas_of_engine(engine_key: str):
    return [e["id"] for e in EAS if e["engine"] == engine_key]


# --- Pacchetti e Portfolio (i veicoli d'acquisto) -------------------------
PACKS = [
    {
        "id": "pack_base", "kind": "pack", "engine": "base",
        "name": {"it": "Pacchetto Base", "en": "Base Pack"},
        "tagline": {"it": "Tutti e 3 gli EA del Motore Base. Diversificazione su EUR/USD, GBP/USD, USD/CHF."},
        "eas": eas_of_engine("base"),
        "price": _price("PACK_BASE", 97),
    },
    {
        "id": "pack_rev", "kind": "pack", "engine": "rev",
        "name": {"it": "Pacchetto Reversione", "en": "Reversion Pack"},
        "tagline": {"it": "Gli EA del Motore Reversione: l'edge raro e decorrelato sui cross."},
        "eas": eas_of_engine("rev"),
        "price": _price("PACK_REV", 67),
    },
]

PORTFOLIO = {
    "id": "portfolio", "kind": "portfolio",
    "name": {"it": "Portfolio PHAI", "en": "PHAI Portfolio"},
    "tagline": {"it": "Tutti i motori, tutti gli EA, AI premium e i nuovi EA inclusi appena escono."},
    "eas": ALL_EA_IDS,
    "price": _price("PORTFOLIO", 197),
}

SINGLE_PRICE = _price("SINGLE_EA", 49)        # prezzo di un singolo EA
SIGNALS_PRICE = _price("SIGNALS", 37)         # solo segnali (esecuzione manuale)


# --- Risoluzione SKU -> EA posseduti --------------------------------------
# Il campo `plan` della licenza è una lista di SKU separati da virgola, p.es.
# "single:EURUSD,single:GBPUSD" oppure "pack_base" oppure "portfolio".
# Sono supportati anche i piani legacy: starter/pro/elite/signals.
def _pack_eas(pack_id: str):
    for p in PACKS:
        if p["id"] == pack_id:
            return list(p["eas"])
    return []


def sku_eas(sku: str):
    """EA (simboli) sbloccati da un singolo SKU. Ritorna lista di id EA."""
    sku = (sku or "").strip().lower()
    if not sku:
        return []
    if sku in ("portfolio", "elite"):
        return list(ALL_EA_IDS)
    if sku == "pro":                       # legacy: Pro = tutti gli EA del Motore Base
        return _pack_eas("pack_base")
    if sku in ("starter", "signals"):      # solo segnali, nessun EA
        return []
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
    """Le 3 opzioni d'acquisto mostrate quando un EA è bloccato (ancoraggio Sabri:
    singolo -> pacchetto del suo motore -> portfolio). Lista di dict ordinata."""
    e = EA_BY_ID.get(ea_id)
    if not e:
        return []
    pack = next((p for p in PACKS if p["engine"] == e["engine"]), None)
    out = [{
        "sku": f"single:{ea_id}", "kind": "single", "title": f"Solo {e['name']}",
        "price": SINGLE_PRICE, "eas": [ea_id], "recommended": False,
    }]
    if pack:
        out.append({
            "sku": pack["id"], "kind": "pack", "title": pack["name"]["it"],
            "price": pack["price"], "eas": list(pack["eas"]), "recommended": True,
        })
    out.append({
        "sku": "portfolio", "kind": "portfolio", "title": PORTFOLIO["name"]["it"],
        "price": PORTFOLIO["price"], "eas": list(ALL_EA_IDS), "best_value": True,
    })
    return out


def is_valid_sku(sku: str) -> bool:
    sku = (sku or "").strip().lower()
    if sku in ("portfolio", "elite", "pro", "signals", "starter"):
        return True
    if sku.startswith("pack_"):
        return any(p["id"] == sku for p in PACKS)
    if sku.startswith("single:"):
        return sku.split(":", 1)[1].upper() in EA_BY_ID
    return False


def sku_label_price(sku: str, lang: str = "it"):
    """(etichetta, prezzo) di uno SKU, per il checkout."""
    sku = (sku or "").strip().lower()
    if sku in ("portfolio", "elite"):
        return (tr(PORTFOLIO["name"], lang), PORTFOLIO["price"])
    if sku in ("signals", "starter"):
        return ("PHAI Signals", SIGNALS_PRICE)
    if sku == "pro":
        p = next((p for p in PACKS if p["id"] == "pack_base"), None)
        return ("PHAI Autopilot", p["price"] if p else 97)
    if sku.startswith("pack_"):
        p = next((p for p in PACKS if p["id"] == sku), None)
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
