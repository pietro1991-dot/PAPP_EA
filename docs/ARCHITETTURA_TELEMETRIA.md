# Architettura telemetria EA → Chatbot (chi scrive dove, chi vede cosa)

> Come i dati degli EA arrivano all'app PHAI e come vengono **isolati per cliente**
> (multi-tenant). Verificato sul codice: `chat_bot/app.py`, `chat_bot/mt5_bridge.py`,
> gli EA in `Singoli/` e `Portafoglio_*/`, e `chat_bot/.env`.

## Concetto chiave

Esistono **DUE canali separati**. Un cliente **non si logga mai sulla VPS owner**:
questa macchina gira **solo** il conto owner. Il cliente usa la SUA macchina/conto e i
dati viaggiano via internet, isolati dalla sua **license key**.

```
┌─────────────────────────── CANALE OWNER (questa VPS) ───────────────────────────┐
│                                                                                  │
│  MT5 (Program Files, portable)         mt5_bridge.py (LogTailer)                 │
│  conto DEMO 52937028 ICMarketsEU        legge Common/Files/papp_ea_*.jsonl       │
│  EA con InpUseServer = FALSE     ──►    (un file PER simbolo, no race)           │
│  scrive file LOCALI                     │                                        │
│                                         ▼                                        │
│                              process_event(data, owner_id=4)                     │
│                              → dati taggati come OWNER (user_id = 4)             │
└──────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────── CANALE CLIENTE (macchina sua) ─────────────────────────┐
│                                                                                   │
│  MT5 del cliente, conto SUO            POST https://app.phai.io/api/ea/ingest     │
│  EA con InpUseServer = TRUE      ──►   body con la SUA license key                │
│  + InpLicenseKey = "sua key"     internet   │                                     │
│                                             ▼                                     │
│                          _resolve_license(key) → used_by_user_id = uid_cliente    │
│                          process_event(ev, uid_cliente)                           │
│                          → dati taggati come QUEL cliente                         │
└───────────────────────────────────────────────────────────────────────────────┘
```

## Canale OWNER (questa VPS) — solo tu

- **MT5**: installazione `C:\Program Files\MetaTrader 5` (portable). Conto loggato:
  **`52937028` su `ICMarketsEU-Demo`** → conto **demo**, broker IC Markets.
- **EA**: `InpUseServer = false` → nessuna licenza, nessuna WebRequest. Scrivono su file.
- **File di log**: `…/Terminal/Common/Files/papp_ea_<SIMBOLO>.jsonl`
  (un file per EA/simbolo: la scrittura concorrente su un file condiviso perdeva righe).
- **Ponte**: `chat_bot/mt5_bridge.py` (`LogTailer`) fa il *tail* di tutti i
  `papp_ea_*.jsonl`, parte dalla fine all'avvio, e per ogni riga chiama la callback.
- **Attribuzione**: `process_event(data, _owner_id())` → **owner = `EA_OWNER_USER_ID=4`**
  (impostato in `chat_bot/.env`).
- **Path del ponte** (in `.env`): `EA_LOG_PATH` deve puntare alla cartella
  `Common/Files` dove l'EA scrive davvero. Oggi combacia. ✅

## Canale CLIENTE — la sua macchina, il suo conto

- Il cliente installa l'EA sul **suo** MetaTrader, sul **suo** conto broker.
- Imposta `InpUseServer = true`, `InpServerUrl = https://app.phai.io`,
  `InpLicenseKey = <la sua key>` (il file `.set` del prodotto lo fa già).
- L'EA invia gli eventi via **WebRequest** a `POST /api/ea/ingest`.
- Il server (`app.py`, riga ~969):
  1. `_resolve_license(key)` valida la key;
  2. `uid = lk.used_by_user_id` → l'utente app collegato alla key;
  3. `process_event(ev, uid)` → dati **taggati come quel cliente**.
- **Protezione anti-misfiling** (riga ~977): se la key **non è ancora collegata** a un
  account app, il server **rifiuta** (`register_app_first`) invece di attribuire i dati
  all'owner. Il cliente deve prima registrare l'app.

## Isolamento multi-tenant (chi vede cosa)

- **`_scope(q, col, user)`** (riga ~100): ogni utente vede **solo i propri dati**
  (`col == user.id`); l'**owner** (e la demo senza owner) vede anche i dati condivisi
  (`col IS NULL`).
- **`_signal_recipients(user_id)`** (riga ~332):
  - segnale dal **master/owner** (user_id None o = owner) → va a **tutti** gli abbonati
    ai segnali (è il prodotto: stessa strategia per tutti);
  - segnale dal **conto di un cliente** → va **solo a quel cliente** (no leak tra tenant).
- **`_user_plan(user)`** (riga ~109): il piano effettivo dipende dalla licenza
  (scaduta/revocata → torna a demo); l'owner ha sempre accesso pieno (`portfolio`).

## Cosa contiene il payload (info + rischio)

Tipi di `action` che fluiscono (contati nei log owner):

| action | contenuto | a cosa serve |
|--------|-----------|--------------|
| `account` | balance, equity, margin, free_margin, margin_level, profit, sym_profit, sym_pct, sym_open | **rischio-conto** live + grafico equity |
| `open` / `close` | entry, sl, tp, lot, pattern, dir, reason | **rischio per-trade** + segnale |
| `state` | osc, dist, vol, to_buy, to_sell, bars_out, info | stato reversione |
| `market` | bid, ask, spread_pts | contesto prezzo/spread |
| `features` | feature di mercato | contesto |
| `skip` | motivo scarto | trasparenza (perché NON ha aperto) |
| `bars` | OHLC D1 del cross | dati GLOBALI per simbolo (uguali per tutti) |

Persistenza scalabile: `_upsert_latest` tiene **una sola riga per (user_id, symbol)**
per lo stato live (spazio fisso); `EquityPoint` campiona l'equity ~1/ora con retention 90gg.

## Modello dati (tag per tenant)

- `AccountSnapshot`, `MarketSnapshot`, `Signal`, `EquityPoint` → hanno `user_id`
  (= tenant). Owner = 4; clienti = il loro id; dati condivisi = NULL.

## ⚠️ Note / punti di attenzione

1. **Il payload NON contiene il numero di conto.** Sul canale owner l'attribuzione è
   "tutto ciò che scrive questa VPS = owner 4". Se MT5 venisse loggato su un altro conto,
   i dati sarebbero comunque attribuiti all'owner. Sui **clienti** invece la separazione
   è robusta (via **license key → user_id**). *Opzionale*: aggiungere il campo `account`
   (login) al JSON dell'EA e far validare al ponte che sia quello atteso.
2. **Switch conto owner** (2026-07-02): da `5051732507` (MetaQuotes-Demo, backtest) a
   **`52937028` (ICMarketsEU-Demo)**, conto madre attuale. I vecchi `.set`/report usano
   ancora 5051732507.

## Servizi (deploy)

- `papp-chat.service` (FastAPI/uvicorn, porta **8090**) — app + `LogTailer` avviato allo startup.
- `opencode-serve.service` — LLM per l'assistente.
- Il `LogTailer` parte dalla **fine** dei file esistenti (non re-ingerisce lo storico):
  se riavvii l'app, i segnali già scritti prima dell'avvio non vengono re-inviati.
