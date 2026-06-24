# 🗺️ Mappa file generati — PaPP EA

Dove finiscono **export, log, CSV e report** prodotti da indicatori, EA e script.
Aggiornato: 2026-06-24.

---

## Istanza MetaTrader: una sola (`~/.wine`)

C'è **una sola** installazione MetaTrader sotto Wine: `~/.wine/drive_c/Program Files/MetaTrader 5`.
Qui vivono storico (EURUSD 1978-2026), EA, indicatore, log e export; i collegamenti desktop
e il chat_bot puntano qui. L'EA v2.05 è deployato in:
`~/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/EA_Pattern.ex5`

> Il vecchio prefisso `~/.mt5` (progetto Mq5_All-in, ora dismesso) è stato **eliminato**.

> Le due cartelle dati di MT5 sono diverse:
> - **Common\Files** (condivisa fra terminali) — usata da chi apre file con flag `FILE_COMMON`
> - **MQL5\Files** (del singolo terminale) — usata da chi NON usa `FILE_COMMON`

---

## 📤 File generati da EA / Indicatori / Export (dentro MetaTrader)

| File | Generato da | Flag | Cartella reale |
|---|---|---|---|
| `papp_ea_log.jsonl` | **EA_Pattern** (decisioni: open/close/skip/market) | `FILE_COMMON` | `~/.wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/` |
| `PAPP_Export.csv` | **Export_PAPP.mq5** (dump barre D1 + MA + cross per il miner) | `FILE_CSV` (no COMMON) | `~/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/` |
| `PaPP_crosses_EURUSD_D1.csv` | Export/indicatore (cross D1) | `FILE_CSV` | `~/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/` |

**Percorsi assoluti (copia-incolla):**
```
# Log decisioni EA
~/.wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/papp_ea_log.jsonl

# Export CSV per l'analisi
~/.wine/drive_c/Program\ Files/MetaTrader\ 5/MQL5/Files/PAPP_Export.csv
```

> 🔎 **Nota backtest (Strategy Tester):** durante un test i file scritti in `MQL5\Files`
> finiscono nella cartella dell'agente di test (`Tester/Agent-*/MQL5/Files/`), **non** in quella
> del terminale. Quelli con `FILE_COMMON` (il log EA) restano invece in **Common\Files**.

---

## 🐍 File generati dall'analisi Python (dentro il progetto)

Cartella: `~/Desktop/PAPP_EA/Analisi/`

| File | Generato da | Note |
|---|---|---|
| `PAPP_Export.csv` | copiato a mano da MQL5\Files | **input** del miner |
| `analisi_completa.txt` | `pattern_mining.py --output=analisi_completa.txt` | analisi vecchia (in-sample, con bias) |
| `analisi_corretta_oos.txt` | `pattern_mining.py ... --split-date=2020.01.01 --output=...` | **analisi corretta** (walk-forward OOS) |

Comando tipico:
```
cd ~/Desktop/PAPP_EA/Analisi
python3 pattern_mining.py PAPP_Export.csv --spread=15 --commission=7 \
        --split-date=2020.01.01 --output=analisi_corretta_oos.txt
```

---

## 🤖 chat_bot (FastAPI + PostgreSQL)

Cartella: `~/Desktop/PAPP_EA/chat_bot/`

| Cosa | Dove | Definito in |
|---|---|---|
| **Legge** il log EA | `~/.wine/.../Common/Files/papp_ea_log.jsonl` (override con env `EA_LOG_PATH`) | `mt5_bridge.py:7` |
| **Database** | PostgreSQL: `postgresql+asyncpg://papp_ea:***@localhost:5432/papp_ea` (override con env `DATABASE_URL`) | `db.py:7` |
| File statici web | `chat_bot/static/` | `app.py:89` |

---

## 🔧 Comandi rapidi per ritrovare i file

```bash
# Tutti i file generati da PaPP (csv/jsonl) nei due prefissi
find ~/.wine/drive_c ~/.mt5/drive_c \( -iname "papp*" -o -iname "PAPP*" \) \
     \( -iname "*.csv" -o -iname "*.jsonl" \) 2>/dev/null

# Ultimo log EA (tail live)
tail -f ~/.wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/papp_ea_log.jsonl

# Cartella dati del terminale reale
ls ~/.wine/drive_c/Program\ Files/MetaTrader\ 5/MQL5/Files/
```

---

## 📁 Sorgenti nel progetto (`~/Desktop/PAPP_EA/`)

| Componente | Sorgente | Compilato (.ex5) deployato in |
|---|---|---|
| EA | `EA/EA_Pattern.mq5` | `~/.wine/.../MQL5/Experts/` |
| Indicatore | `Indicatori/PaPP_Median.mq5` | `~/.wine/.../MQL5/Indicators/` |
| Export dati | `Analisi/Export_PAPP.mq5` | `~/.wine/.../MQL5/Indicators/` o `Scripts/` |
| Miner | `Analisi/pattern_mining.py` | — (Python) |
| Chat bot | `chat_bot/*.py` | — (Python) |
