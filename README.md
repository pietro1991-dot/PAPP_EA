# PAPP_EA — Sistema di trading multi-simbolo (motore base linea-prezzo)

Sistema basato su **crossover di medie mobili ancorate al giornaliero (D1)**, prodotte
dall'indicatore `PHAI_Median`. Il codice (indicatore, export, miner) è **condiviso**; i
**pattern validati** e i **dati** sono per-simbolo, con una **copia dell'EA per simbolo**.

> **Motore base linea-prezzo**: gli EA entrano/escono solo su **crossover prezzo-linea**
> (il prezzo che taglia una media o la mediana) e usano stop su linea o a distanza fissa.
> I pattern **linea-linea** (due medie che si incrociano tra loro) restano calcolati dal
> miner ma **nessun EA li trada**.

## Struttura cartelle

```
PAPP_EA/
├── Motore base _linea-prezzo/        ← IL SISTEMA ATTUALE
│   ├── Indicatore/                     codice e doc CONDIVISI
│   │   ├── PHAI_Median.mq5 (+.ex5)       indicatore (7 MA + mediana, ancorato D1)
│   │   ├── INDICATORE_PHAI_Median.md     → come funziona l'indicatore
│   │   ├── Export_PAPP.mq5 (+.ex5)       script: esporta il CSV per il miner
│   │   ├── EXPORT_PAPP.md                → come funziona l'export
│   │   ├── pattern_mining.py             miner: trova e valida i pattern
│   │   ├── MINER_pattern_mining.md       → come funziona il miner
│   │   └── genera_schede.py              genera PATTERNS_<SIMBOLO>.md (schede pattern + stat)
│   │
│   ├── EURUSD/   EA_EURUSD.mq5 (+.ex5) · PAPP_Export.csv · OHLC · analisi_oos.txt · PATTERNS_EURUSD.md
│   ├── GBPUSD/   EA_GBPUSD.mq5 (+.ex5) · PAPP_Export_GBPUSD.csv · analisi_oos.txt · PATTERNS_GBPUSD.md · _TODO.md
│   └── USDCHF/   EA_USDCHF.mq5 (+.ex5) · PAPP_Export_USDCHF.csv · analisi_oos.txt · PATTERNS_USDCHF.md · _TODO.md
│
├── chat_bot/      assistant FastAPI/PostgreSQL (legge il log dell'EA)
├── docs/          DOCUMENTAZIONE.md (completa), MAPPA_FILE.md (dove vivono i file generati)
├── trading/       asset di branding
└── Legacy/        vecchi EA, script, dati e indicatori non più usati (archivio)
```

## La pipeline in 4 passi

```
Indicatore  →  Export  →  Miner  →  EA
(7 MA + mediana    (CSV per       (trova/valida    (trada i pattern
 ancorate D1)       barra)         i pattern OOS)    validati per simbolo)
```

1. **Indicatore** `PHAI_Median`: calcola 7 medie + la loro mediana, tutto su D1.
2. **Export** `Export_PAPP`: salva una riga per barra (prezzi, medie, crossover, metriche) in CSV.
3. **Miner** `pattern_mining.py`: prova le combinazioni di entrata/uscita, le valida su
   train+test (anti-overfitting), e produce `analisi_oos.txt`.
4. **EA** del simbolo: ha nei default i pattern validati e li trada.

Dettagli in [Motore base _linea-prezzo/Indicatore/](Motore%20base%20_linea-prezzo/Indicatore/)
(tre documenti: indicatore, export, miner).

## Aggiungere un nuovo simbolo (es. AUDUSD)

1. **Esporta i dati**: esegui `Export_PAPP` su un grafico **AUDUSD D1** in MT5
   (genera `PAPP_Export.csv` in `MQL5/Files`). Copialo in una nuova cartella
   `Motore base _linea-prezzo/AUDUSD/`.
2. **Trova e valida i pattern**:
   ```
   cd "Motore base _linea-prezzo/AUDUSD"
   python3 "../Indicatore/pattern_mining.py" PAPP_Export.csv \
           --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
   ```
   Tieni solo i pattern **positivi out-of-sample** (sezione SELEZIONE ROBUSTA).
3. **Crea l'EA**: copia un `EA_*.mq5` esistente → `EA_AUDUSD.mq5` e imposta nei default
   i pattern validati per AUDUSD.
4. **Genera la scheda dei pattern** (statistiche per pattern + appendice candidati):
   ```
   python3 "../Indicatore/genera_schede.py" PAPP_Export.csv EA_AUDUSD.mq5 AUDUSD \
           --split=2020.01.01 --spread=15 --comm=7
   ```
   → produce `PATTERNS_AUDUSD.md`, sempre allineato all'EA e ai dati.
5. **Compila e backtesta** in MT5 sul grafico AUDUSD.

> ⚠️ **Manutenzione**: avendo una copia EA per simbolo, una correzione alla *logica* va
> propagata a tutte le copie `EA_*.mq5`. I pattern invece restano indipendenti per simbolo.

## Stato dei simboli

| Simbolo | EA | Motore | Pattern |
|---|---|---|---|
| EURUSD | EA_EURUSD | base | SL=MA365 + TP stretto (validati OOS) |
| GBPUSD | EA_GBPUSD | base | SELL su cross + disaster stop |
| USDCHF | EA_USDCHF | base | SELL→crossMA182 + TP, BUY, GRID |

Tutti e tre a **motore base** (solo prezzo-linea). Dettagli e analisi in `analisi_oos.txt`
e `_TODO.md` di ciascun simbolo.
