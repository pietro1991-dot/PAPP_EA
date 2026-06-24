# PAPP_EA — Sistema multi-simbolo

Sistema di trading basato su crossover di MA ancorate al D1 (indicatore `PaPP_Median`).
Organizzato per **scalare a più simboli**: il codice è condiviso, i pattern e i dati sono per-simbolo.

## Struttura cartelle

```
PAPP_EA/
├── src/                    ← CODICE CONDIVISO (uguale per ogni simbolo)
│   ├── indicators/         PaPP_Median.mq5 (+.ex5), PaPP_Projection.mq5
│   ├── scripts/            Export_PAPP.mq5 (+.ex5)  → esporta il CSV
│   └── analysis/           pattern_mining.py        → trova/valida i pattern
│
├── symbols/                ← SPECIFICO PER SIMBOLO (un EA per simbolo)
│   └── EURUSD/
│       ├── EA_EURUSD.mq5 (+.ex5)   EA coi pattern validati per EURUSD
│       ├── PAPP_Export.csv          dati esportati (D1)
│       └── analisi_oos.txt          output del miner (walk-forward)
│   └── <NUOVO_SIMBOLO>/    ← stessa struttura per ogni nuovo grafico
│
├── chat_bot/               ← assistant FastAPI/PostgreSQL (legge il log EA)
├── docs/                   DOCUMENTAZIONE.md, MAPPA_FILE.md
└── Legacy/                 vecchi EA/script (archivio)
```

**Principio:** indicatore, script di export e miner sono **identici** per ogni simbolo
(stanno in `src/`). Ciò che cambia per simbolo — i dati e soprattutto i **pattern validati** —
sta in `symbols/<SIMBOLO>/`, con una **copia dell'EA per simbolo** (i pattern sono input
hard-coded nei default di quel file).

## Aggiungere un nuovo simbolo (es. GBPUSD)

1. **Esporta i dati**: apri `src/scripts/Export_PAPP.mq5` su un grafico **GBPUSD D1** in MT5
   (genera `PAPP_Export.csv` in `MQL5/Files`). Copialo in `symbols/GBPUSD/PAPP_Export.csv`.
2. **Trova/valida i pattern** (walk-forward + costi):
   ```
   cd symbols/GBPUSD
   python3 ../../src/analysis/pattern_mining.py PAPP_Export.csv \
           --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
   ```
   Tieni solo i pattern **positivi out-of-sample** (colonna TEST).
3. **Crea l'EA del simbolo**: copia `symbols/EURUSD/EA_EURUSD.mq5` →
   `symbols/GBPUSD/EA_GBPUSD.mq5` e imposta nei default i pattern validati per GBPUSD.
4. **Compila e backtesta** in MT5 sul grafico GBPUSD.

> ⚠️ **Nota manutenzione**: avendo una copia EA per simbolo, una correzione alla *logica*
> dell'EA va propagata a tutte le copie `symbols/*/EA_*.mq5`. I pattern invece restano
> indipendenti per simbolo.

## Stato EURUSD (riferimento)
EA v2.08 — 10 pattern validati OOS: 6 con SL+TP (P1–P6) + 4 a incrocio MA121 con TP cap 1500 (P7–P10).
Dettagli in [docs/DOCUMENTAZIONE.md](docs/DOCUMENTAZIONE.md). Percorsi file generati in [docs/MAPPA_FILE.md](docs/MAPPA_FILE.md).
