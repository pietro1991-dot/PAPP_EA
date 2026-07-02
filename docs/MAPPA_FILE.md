# 🗺️ Mappa file generati — PaPP EA

Dove finiscono **export, log, CSV e report** prodotti da indicatore, EA e script.

---

## Istanza MetaTrader: una sola (`~/.wine`)

C'è **una sola** installazione MetaTrader sotto Wine:
`~/.wine/drive_c/Program Files/MetaTrader 5`.
Qui vivono storico, EA, indicatore, log ed export; i collegamenti desktop e il chat_bot
puntano qui.

> Le due cartelle dati di MT5 sono diverse:
> - **Common\Files** (condivisa fra terminali) — usata da chi apre file con flag `FILE_COMMON`
> - **MQL5\Files** (del singolo terminale) — usata da chi NON usa `FILE_COMMON`

---

## 📤 File generati dentro MetaTrader (EA / indicatore / export)

| File | Generato da | Flag | Cartella reale |
|---|---|---|---|
| `papp_ea_log.jsonl` | **EA del simbolo** (decisioni: open/close/skip/market) | `FILE_COMMON` | `~/.wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/` |
| `PAPP_Export.csv` | **Export_PAPP.mq5** (dump barre D1 + MA + cross + metriche per il miner) | `FILE_CSV` (no COMMON) | `~/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/` |

**Percorsi assoluti (copia-incolla):**
```
# Log decisioni EA
~/.wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/papp_ea_log.jsonl

# Export CSV per l'analisi
~/.wine/drive_c/Program\ Files/MetaTrader\ 5/MQL5/Files/PAPP_Export.csv
```

> 🔎 **Nota backtest (Strategy Tester):** durante un test i file scritti in `MQL5\Files`
> finiscono nella cartella dell'agente (`Tester/Agent-*/MQL5/Files/`), **non** in quella del
> terminale. Quelli con `FILE_COMMON` (il log EA) restano invece in **Common\Files**.
> Il risultato del test (balance, trade) sta nella cache del tester e nei log dell'agente
> (`Tester/Agent-*/logs/AAAAMMGG.log`), non nel CSV.

---

## 🐍 Analisi Python (dentro il progetto)

Il miner si lancia dalla cartella del simbolo, leggendo il CSV esportato:
```
cd "Motore base _linea-prezzo/<SIMBOLO>"
python3 "../Indicatore/pattern_mining.py" PAPP_Export.csv \
        --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
```
Output: `analisi_oos.txt` nella cartella del simbolo (il report con la SELEZIONE ROBUSTA).

---

## 🤖 chat_bot (FastAPI + PostgreSQL)

Cartella: `chat_bot/`

| Cosa | Dove | Definito in |
|---|---|---|
| **Legge** il log EA | `~/.wine/.../Common/Files/papp_ea_log.jsonl` (override con env `EA_LOG_PATH`) | `mt5_bridge.py` |
| **Database** | PostgreSQL (override con env `DATABASE_URL`) | `db.py` |
| File statici web | `chat_bot/static/` | `app.py` |

---

## 🔧 Comandi rapidi

```bash
# Tutti i file PaPP generati (csv/jsonl) in MT5
find ~/.wine/drive_c \( -iname "papp*" -o -iname "PAPP*" \) \
     \( -iname "*.csv" -o -iname "*.jsonl" \) 2>/dev/null

# Ultimo log EA (tail live)
tail -f ~/.wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/papp_ea_log.jsonl

# Cartella dati del terminale reale
ls ~/.wine/drive_c/Program\ Files/MetaTrader\ 5/MQL5/Files/
```

---

## 📁 Sorgenti nel progetto (`~/Desktop/PAPP_EA/`)

| Componente | Sorgente | Compilato (.ex5) deployato in MT5 |
|---|---|---|
| Indicatore | `Motore base _linea-prezzo/Indicatore/PHAI_Median.mq5` | `~/.wine/.../MQL5/Indicators/` |
| Export dati | `Motore base _linea-prezzo/Indicatore/Export_PAPP.mq5` | `~/.wine/.../MQL5/Scripts/` |
| Miner | `Motore base _linea-prezzo/Indicatore/pattern_mining.py` | — (Python) |
| EA (per simbolo) | `Motore base _linea-prezzo/<SIMBOLO>/EA_<SIMBOLO>.mq5` | `~/.wine/.../MQL5/Experts/` |
| Chat bot | `chat_bot/*.py` | — (Python) |

> Nota: in MT5 le copie dell'EA possono avere nomi diversi dal sorgente (es. `svizzero_4`):
> conta il *contenuto* (i pattern), non il nome del file.
