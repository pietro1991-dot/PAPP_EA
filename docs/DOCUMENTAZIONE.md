# PAPP_EA — Documentazione Completa

## Indice

0. [⭐ STATO CORRENTE — leggi prima](#-stato-corrente--leggi-prima)
1. [Visione d&#39;Insieme](#1-visione-dinsieme)
2. [Pipeline dei Dati](#2-pipeline-dei-dati)
3. [Il Dataset: PAPP_Export.csv](#3-il-dataset-papp_exportcsv)
4. [Pattern Mining — Le Tre Analisi](#4-pattern-mining--le-tre-analisi)
5. [Analisi 1: Crossover → Qualsiasi Crossover Opposto](#5-analisi-1-crossover--qualsiasi-crossover-opposto)
6. [Analisi 2: Crossover → Crossover su Linea Specifica](#6-analisi-2-crossover--crossover-su-linea-specifica)
7. [Analisi 3: Grid Search SL Dinamico + TP Fisso](#7-analisi-3-grid-search-sl-dinamico--tp-fisso)
8. [Risultati Completi delle Analisi](#8-risultati-completi-delle-analisi)
9. [Architettura dell&#39;EA](#9-architettura-dellea)
10. [Pattern Dettagliati](#10-pattern-dettagliati)
11. [Risk Management](#11-risk-management)
12. [Guida all&#39;Uso](#12-guida-alluso)
13. [Walk-Forward Validation](#13-walk-forward-validation)
14. [Limitazioni e Rischi Noti](#14-limitazioni-e-rischi-noti)

---

## ⭐ STATO CORRENTE — LEGGI PRIMA

> **Struttura attuale**: tutto il sistema vive in `Motore base _linea-prezzo/`. Dentro:
> `Indicatore/` (indicatore + export + miner, ognuno con la sua doc) e **una cartella per
> simbolo** (`EURUSD/`, `GBPUSD/`, `USDCHF/`) con EA, dati e `analisi_oos.txt`.
>
> Per **come funzionano** i singoli componenti, i riferimenti aggiornati sono i tre documenti
> in `Motore base _linea-prezzo/Indicatore/`:
> `INDICATORE_PHAI_Median.md`, `EXPORT_PAPP.md`, `MINER_pattern_mining.md`.
> Questo file resta la documentazione **tecnica del sistema** (le 3 analisi, architettura EA,
> risk management, limitazioni). Le sezioni 5–10 descrivono l'esplorazione storica: vanno
> lette come contesto, la configurazione attiva è nei default di ogni EA.

> **Motore base linea-prezzo**: tutti gli EA entrano/escono solo su crossover **prezzo-linea**
> (il prezzo che taglia una media o la mediana); i pattern **linea-linea** (due medie che si
> incrociano) sono calcolati dal miner ma **nessun EA li trada**.

### A. Correzioni di metodologia al pattern miner (valide tuttora)

Erano presenti bias che gonfiavano i risultati. Corretti in `pattern_mining.py`:

| Bug | Prima | Dopo |
| --- | --- | --- |
| **Sharpe** | annualizzato `×√252` su trade sporadici → gonfiato ~15× | **Sharpe per-trade** (`avg/sd`) |
| **Look-ahead SL** | usava la MA della stessa barra di cui testava high/low | usa la MA della **barra precedente** (`rows[j-1]`) |
| **Sharpe finto** | valore enorme con varianza quasi nulla (TP minuscoli) | `0` (CV<10% → azzerato) |
| **Censoring** | trade non risolti scartati (non contati come perdite) | chiusura **TIMEOUT** mark-to-market |
| **Costi** | solo spread | `--commission` e `--swap` per barra |

Comando di riferimento (walk-forward + costi):
```
python3 "../Indicatore/pattern_mining.py" PAPP_Export.csv --spread=15 --commission=7 \
        --split-date=2020.01.01 --output=analisi_oos.txt
```

**Effetto:** i numeri spettacolari erano artefatti. I pattern cross-exit puri (Analisi 1/2,
senza SL/TP) spesso **crollano out-of-sample** → vanno tenuti solo quelli della **SELEZIONE
ROBUSTA** (positivi su train *e* test).

### B. Configurazione: un EA per simbolo, tutti a motore base

Non c'è più un'unica configurazione: **ogni simbolo ha il suo EA** coi pattern validati OOS
hard-coded nei default. In sintesi (i numeri esatti sono in ciascun `analisi_oos.txt`/`_TODO.md`):

| Simbolo | Idea dei pattern |
| --- | --- |
| **EURUSD** | entry cross + **SL=MA365 (linea) + TP stretto** (profilo alto-win) |
| **GBPUSD** | SELL su **exit-cross** + **disaster stop a distanza fissa** (`InpPx_SLpips`) |
| **USDCHF** | SELL → crossMA182 con **TP**, un BUY trend, un BUY GRID (SL=MA121+TP) |

⚠️ Profilo **alto-win / perdita-rara-ma-grande** quando lo SL è lontano (MA365): sizing e
gestione del rischio sono decisivi (vedi §11).

### C. Stop: su linea + a distanza fissa (entrambi prezzo-based)

- **SL su linea** (`InpPx_SL`): `UpdateDynamicSL()` trascina lo stop sul **valore corrente della
  MA** (shift 1 = barra chiusa, niente look-ahead); se la linea raggiunge il prezzo, chiude.
- **Disaster stop fisso** (`InpPx_SLpips`): stop a N pip fissi dall'entrata (taglia le code).
- **TP fisso** (`InpPx_TP`) broker-side.
- Sono **tutti prezzo vs linea o vs livello**: nessuno stop linea-linea.

### D. Export coerente con l'EA (Export_PAPP.mq5 v2.04)

- `iCustom` con gli **stessi parametri dell'EA** (`Smooth=false`, `InpSignals=true` → valori MA
  **raw a gradino**), identici in ogni timeframe e senza look-ahead.
- `cluster%` = valore della **barra corrente**; `vel%`/`acc%` **con segno**; aggiunte le colonne
  **percentile** `cluPct/velPct/accPct/volPct` (allineato all'indicatore v2.01).
- ➡️ Rigenerare il CSV **solo su grafico D1** (o con `InpSignals=true`).

### E. Ambiente

- **Un solo** prefisso MetaTrader: `~/.wine`. Mappa completa dei percorsi in **`MAPPA_FILE.md`**.

### F. Sizing configurabile

- `InpRiskPct` (% di rischio per trade) + `InpMaxLot` (tetto al lotto).
- `InpFallbackRiskPips` = distanza di rischio usata per il sizing **quando un pattern non ha SL**
  (es. i pattern a solo cross-exit/TP): va impostata vicino all'escursione avversa reale.

---

## 1. Visione d'Insieme

PAPP_EA è un sistema di trading algoritmico per MetaTrader 5 basato su **crossover di medie mobili calcolate su timeframe giornaliero (D1)**. Utilizza l'indicatore personalizzato `PHAI_Median.ex5` che analizza 8 linee sul prezzo EURUSD:

| Linea            | Periodo | Nome nel codice    | Descrizione                                                   |
| ---------------- | ------- | ------------------ | ------------------------------------------------------------- |
| **Median** | 0       | `BUF_MEDIAN` (0) | Mediana del prezzo D1 (valore centrale del range giornaliero) |
| **MA3**    | 3       | `BUF_MA3` (7)    | Media mobile semplice a 3 giorni                              |
| **MA7**    | 7       | `BUF_MA7` (6)    | Media mobile semplice a 7 giorni (~1 settimana)               |
| **MA14**   | 14      | `BUF_MA14` (5)   | Media mobile semplice a 14 giorni (~2 settimane)              |
| **MA30**   | 30      | `BUF_MA30` (4)   | Media mobile semplice a 30 giorni (~1 mese)                   |
| **MA121**  | 121     | `BUF_MA121` (3)  | Media mobile semplice a 121 giorni (~6 mesi)                  |
| **MA182**  | 182     | `BUF_MA182` (2)  | Media mobile semplice a 182 giorni (~9 mesi)                  |
| **MA365**  | 365     | `BUF_MA365` (1)  | Media mobile semplice a 365 giorni (~1 anno)                  |

Il sistema opera in due fasi distinte ma collegate:

**Fase 1 — Pattern Mining (offline, Python)**:
Lo script `Analisi/pattern_mining.py` carica 4278 barre D1 di EURUSD (2009–2026), rileva automaticamente tutti i crossover e applica tre metodologie di analisi per identificare configurazioni profittevoli di entrata/uscita/SL/TP. Genera tabelle con Sharpe ratio, Win Rate, Profit Factor, numero di trade e durata media.

**Fase 2 — Esecuzione (online, MQL5)**:
L'EA `EA/EA_Pattern.mq5` carica fino a 10 pattern configurabili via input e li esegue simultaneamente sul mercato reale. Ogni pattern può avere una linea di entrata, una linea d'uscita (crossover), una linea SL (hard + dinamico) e un TP fisso. Il risk management è completamente configurabile.

---

## 2. Pipeline dei Dati

Il flusso dei dati è lineare:

```
Export_PAPP.mq5 (MQL5 su MT5)
        ↓
PAPP_Export.csv (4278 barre D1, 2009–2026)
        ↓
pattern_mining.py (Python, 3 analisi)
        ↓
Risultati → configurazione manuale degli input dell'EA
        ↓
EA_Pattern.mq5 (MQL5, esecuzione in tempo reale)
```

### 2.1 Esportazione — Export_PAPP.mq5

Script MQL5 puro (`#property script_show_inputs`, funzioni `OnStart()`) che:

1. Si connette all'indicatore `PHAI_Median.ex5` su EURUSD D1
2. Itera su tutte le barre D1 disponibili nel history
3. Per ogni barra, calcola:
   - **Prezzi OHLC**: open, high, low, close
   - **Valori delle 8 linee**: median, MA3, MA7, MA14, MA30, MA121, MA182, MA365
   - **Distanze percentuali**: `dMed%`, `d3%`, ..., `d365%` = `(close - linea) / close × 100`
   - **Flag above/below**: `aMed`, `a3`, ..., `a365` = 1 se close > linea, 0 altrimenti
   - **Crossover**: `crossMed`, `crossMA3`, ..., `crossMA365` = +1 (bullish), −1 (bearish), 0 (nessuno)
   - **Metriche contestuali**: `cluster%`, `vel%`, `acc%`, `vol%`, `orderScore`, `spread`, `spreadVel`
   - **Spread tra MA**: `MA3_7`, `MA7_14`, `MA14_30`, `MA30_121`, `MA121_182`, `MA182_365`
   - **Medie contestuali**: `fastAvg` (media di MA3/7/14), `slowAvg` (media di MA121/182/365)

### 2.2 Pattern Mining — pattern_mining.py

Script Python v3 che esegue tre analisi indipendenti sui dati esportati.

**Parametri da riga di comando**:

```
python3 pattern_mining.py PAPP_Export.csv [opzioni]

Opzioni:
  --spread=N           Spread in punti (default: 15 = 1.5 pip EURUSD)
  --train-pct=N        Percentuale per training (default: 1.0 = 100%)
  --split-date=...     Cutoff train/test (sovrascrive train-pct)
  --min-trades=N       Minimo trade per pattern valido (default: 10)
  --debug=N            Stampa primi N trade per debug manuale

Filtri contestuali:
  min_cluster=N   max_cluster=N    (cluster% range)
  min_vel=N       max_vel=N        (vel% range)
  min_vol=N       max_vol=N        (vol% range)
  min_orderScore=N  max_orderScore=N
  min_spread=N    max_spread=N
  min_dMed=N      max_dMed=N
  longBelow=1     longAbove=1
```

**Spread**: ogni trade subisce una detrazione fissa in punti. Default 15pt = 1.5 pip, che è lo spread tipico EURUSD su D1. Questo è cruciale perché spread troppo alti erodono i profitti dei pattern a basso PnL medio.

**Walk-forward**: possibilità di dividere in training set (es. 70%) e test set (30%) con `--train-pct=0.7` o `--split-date=2020.01.01`. I migliori pattern del training vengono validati sul test.

**Funzionamento interno**:

```python
# Rilevamento entrate
for each bar in bars:
    for each line in [MA365, MA182, ..., Median]:
        if cross_column[bar] != 0:  # +1 bullish, -1 bearish
            entries.append({
                'idx': bar_index,
                'line': line_name,
                'dir': cross_val,
                'price': bar.close,
                'datetime': bar.datetime,
                'ctx': context_metrics  # cluster%, vel%, vol%, ...
            })
```

### 2.3 Metriche di Valutazione

| Metrica                 | Formula SQL                            | Implementazione Python                                                         |
| ----------------------- | -------------------------------------- | ------------------------------------------------------------------------------ |
| **Sharpe (per-trade)** | `mean(pnls) / stdev(pnls)` | **NON** annualizzato. Se std=0 → 0 (artefatto). |
| **Win Rate**      | `COUNT(pnl>0) / COUNT(*) × 100`     | Percentuale trade positivi                                                     |
| **Profit Factor** | `SUM(pnl>0) / ABS(SUM(pnl<0))`       | `sum(pos) / max(1, abs(sum(neg)))`                                           |
| **Avg PnL**       | `AVG(pnl)`                           | Media in punti. Positivo = profittevole                                        |
| **Total PnL**     | `SUM(pnl)`                           | Profitto netto totale in punti                                                 |
| **Avg Bars**      | `AVG(bars_held)`                     | Durata media in giorni D1                                                      |

**Nota sullo Sharpe**: è **per-trade** (`avg/sd`, senza annualizzazione). La vecchia versione
moltiplicava per `√252` assumendo 252 trade/anno: su pattern che fanno ~3-5 trade/anno questo
**gonfiava il valore di ~10-15×**. Per annualizzare correttamente: `× √(trade per anno)`.
Quando la varianza è nulla (es. TP minuscolo sempre colpito) lo Sharpe ora vale 0 (era 99 = finto).
Riferimento: Sharpe per-trade > 1 è già molto buono per questo tipo di strategia sporadica.

---

## 3. Il Dataset: PAPP_Export.csv

### 3.1 Struttura del File

```
Colonne (56 totali):
  datetime, open, high, low, close,
  median, MA365, MA182, MA121, MA30, MA14, MA7, MA3,
  dMed%, d365%, d182%, d121%, d30%, d14%, d7%, d3%,
  a365, a182, a121, a30, a14, a7, a3, aMed,
  fastAvg, slowAvg, spread, spreadVel, orderScore,
  s14_30, s7_30, longBelow, longAbove,
  cluster%, vel%, acc%, vol%,
  crossMA365, crossMA182, crossMA121, crossMA30, crossMA14, crossMA7, crossMA3, crossMed,
  MA3_7, MA7_14, MA14_30, MA30_121, MA121_182, MA182_365
```

### 3.2 Prime 5 Barre (Esempio Raw)

```
2009.12.31  open=1.43365  close=1.43306  MA365=1.39436  MA3=1.43333
2010.01.04  open=1.43259  close=1.44111  MA365=1.39455  MA3=1.43709
2010.01.05  open=1.44107  close=1.43624  MA365=1.39483  MA3=1.43868
2010.01.06  open=1.43632  close=1.43998  MA365=1.39518  MA3=1.43811
2010.01.07  open=1.43974  close=1.44076  MA365=1.39548  MA3=1.44043
```

### 3.3 Significato delle Colonne Chiave

| Colonna        | Tipo             | Descrizione                                                                                                     |
| -------------- | ---------------- | --------------------------------------------------------------------------------------------------------------- |
| `crossMA_X`  | int {−1, 0, +1} | +1 = prezzo chiude sopra MA (bullish cross). −1 = prezzo chiude sotto MA (bearish cross). 0 = nessun crossover |
| `dX%`        | float            | Distanza percentuale:`(close − MA_X) / close × 100`. Positivo = prezzo sopra MA                             |
| `aX`         | int {0, 1}       | 1 = prezzo sopra MA (above). 0 = prezzo sotto MA (below)                                                        |
| `longBelow`  | int {0, 1}       | 1 = prezzo sotto la maggior parte delle MA lunghe (contesto ribassista)                                         |
| `longAbove`  | int {0, 1}       | 1 = prezzo sopra la maggior parte delle MA lunghe (contesto rialzista)                                          |
| `cluster%`   | float            | Quanto le MA sono raggruppate (basso = allineate, alto = disperse)                                              |
| `vel%`       | float            | Velocità di movimento del prezzo rispetto alla media storica                                                   |
| `vol%`       | float            | Volume relativo (rispetto alla media)                                                                           |
| `orderScore` | int              | Allineamento delle MA (valore alto = forte trend)                                                               |
| `MA3_7`      | float            | Distanza in punti tra MA3 e MA7 (espansione/contrazione)                                                        |

### 3.4 Statistiche del Dataset

```
Barre totali:     4278
Data inizio:      2009.12.31
Data fine:        2026.06.19
Anni coperti:     16.5
Prezzo min:       ~1.0400 (2015, 2022)
Prezzo max:       ~1.6000 (2008, fuori campione)
Prezzo medio:     ~1.2100
Segnali totali:   5967 (cross bull + cross bear)
Segnali BUY:      2983
Segnali SELL:     2984
Segnali per linea:
  MA365:    119  (rari, ~7/anno)
  MA182:    188  (~11/anno)
  MA121:    242  (~15/anno)
  MA30:     506  (~31/anno)
  MA14:     743  (~45/anno)
  MA7:     1116  (~68/anno)
  MA3:     2183  (~132/anno)
  Median:   870  (~53/anno)
```

La MA3 genera il maggior numero di segnali (2183) perché è la più reattiva. La MA365 ne genera solo 119 perché il prezzo impiega molto tempo ad attraversare la media annuale.

---

## 4. Pattern Mining — Le Tre Analisi

Lo script esegue tre analisi indipendenti, ognuna con una logica di exit diversa. Possono essere considerate come tre strategie separate testate sullo stesso dataset.

### Schema Riassuntivo

```
Analisi 1: Entry(cross) → Exit(primo cross opposto su qualsiasi linea)
   ↑ reattiva, trade brevi, cattura trend puri
   
Analisi 2: Entry(cross) → Exit(cross opposto su linea SPECIFICA)
   ↑ mirata, trade medi, resiste a crossover contrari su altre scale
   
Analisi 3: Entry(cross) → SL dinamico su linea + TP fisso
   ↑ risk-defined, trade variabili, R:R noto
```

---

## 5. Analisi 1: Crossover → Qualsiasi Crossover Opposto

### 5.1 Logica

```python
for each entry_signal:
    buy = (direction == +1)
    entry_price = bar.close
  
    for each subsequent_bar:
        for each line in [MA3, MA7, ..., MA365, Median]:
            if line has crossover in OPPOSITE direction:
                # BUY aperto → cerchiamo bearish cross
                # SELL aperto → cerchiamo bullish cross
                close_position()
                break  # esce al primo cross opposto
```

L'idea è: **entra nella direzione del crossover, esci al primo segnale contrario su qualsiasi orizzonte temporale**.

### 5.2 Risultati corretti (per-trade, walk-forward)

Con la metodologia corretta (Sharpe **per-trade**, no look-ahead, costi inclusi), i pattern di
Analisi 1 hanno Sharpe molto basso. Top (train ≤2020):

| Entry | Dir | Trades | Win% | AvgPts | Sharpe |
| --- | --- | --- | --- | --- | --- |
| MA365 | SELL | 32 | 50.0% | +248 | 0.21 |
| MA7 | SELL | 339 | 36.6% | +26 | 0.02 |
| MA30 | SELL | 158 | 36.1% | +1 | 0.00 |

⚠️ **Out-of-sample (test >2020) CROLLANO**: win ~50%→35%, Sharpe→~0/negativo.
➡️ **Analisi 1 scartata** — nessun pattern usato nell'EA. Tabelle complete in `analisi_corretta_oos.txt`.


## 6. Analisi 2: Crossover → Crossover su Linea Specifica

### 6.1 Logica

```python
for each entry_signal:
    buy = (direction == +1)
  
    for each exit_line in [MA3, MA7, ..., MA365, Median]:
        exit_cross_col = f"crossMA{exit_line}"
      
        for each subsequent_bar:
            cv = bar[exit_cross_col]
            if cv == 0:
                continue
            if buy and cv == −1:  # bearish cross = chiudi BUY
                close_position()
                break
            if not buy and cv == +1:  # bullish cross = chiudi SELL
                close_position()
                break
```

L'idea è: **entra nella direzione del crossover, esci solo quando una linea SPECIFICA (non qualsiasi) fa un crossover contrario**.

### 6.2 Risultati corretti (per-trade, walk-forward)

I pattern cross→cross specifico mostrano TotPnl alti ma con tenute lunghe (decine di barre →
swap pesante) e Sharpe per-trade basso. Top (train ≤2020):

| Entry | Dir | Exit | Trades | Win% | Sharpe |
| --- | --- | --- | --- | --- | --- |
| MA365 | BUY | crossMA121 | 29 | 65.5% | 0.24 |
| MA365 | SELL | crossMA7 | 32 | 46.9% | 0.23 |
| MA30 | SELL | crossMA121 | 152 | 46.7% | 0.21 |

⚠️ **Out-of-sample CROLLANO** (win→~36%, Sharpe→~0/negativo).
➡️ **Analisi 2 scartata** — nessun pattern usato nell'EA. Dettagli in `analisi_corretta_oos.txt`.


## 7. Analisi 3: Grid Search SL Dinamico + TP Fisso

### 7.1 Logica

```python
for each entry_signal:
    buy = (direction == +1)
    entry_price = bar.close
  
    for each sl_line in [MA14, MA30, MA121, MA365, Median]:
        sl_value = bar[sl_line]
      
        # Verifica SL dalla parte giusta
        if buy and sl_value >= entry_price: continue  # SL sopra entry? skip
        if not buy and sl_value <= entry_price: continue
      
        for each tp_pt in [20, 30, 40, 50, 60, 80, 100, 120, 150]:
          
            for each subsequent_bar:
                bar_high = bar.high
                bar_low  = bar.low
                sl_value_current = bar[sl_line]  # SL DINAMICO: si aggiorna ogni barra
              
                if buy and bar_low <= sl_value_current:
                    exit_price = sl_value_current
                    pnl = (exit_price - entry_price) / PT_SIZE - spread
                    # Uscita per SL (prezzo tocca la linea)
                  
                if not buy and bar_high >= sl_value_current:
                    exit_price = sl_value_current
                    pnl = (entry_price - exit_price) / PT_SIZE - spread
                    # Uscita per SL
                  
                if buy and bar_high >= (entry_price + tp_pt * PT_SIZE):
                    pnl = tp_pt - spread
                    # Uscita per TP
                  
                if not buy and bar_low <= (entry_price - tp_pt * PT_SIZE):
                    pnl = tp_pt - spread
                    # Uscita per TP
```

**SL dinamico**: a differenza di uno SL statico, il valore della linea SL viene riletto a ogni barra. Se la linea sale (trend rialzista), lo SL sale con essa. Questo protegge il profitto in modo naturale.

### 7.2 Risultati corretti (per-trade) — base dell'EA

Analisi 3 (entry cross + SL dinamico su linea + TP fisso) è l'**unica** che regge OOS. Top per
Sharpe per-trade (train ≤2020):

| Entry | Dir | SL | TP | Trades | Win% | Sharpe |
| --- | --- | --- | --- | --- | --- | --- |
| MA30 | BUY | MA365 | 150 | 62 | 98.4% | 2.47 |
| MA30 | BUY | MA365 | 120 | 62 | 98.4% | 2.03 |
| MA365 | BUY | MA30 | 150 | 20 | 90.0% | 1.09 |
| MA14 | SELL | MA365 | 50 | 130 | 98.5% | 0.64 |
| MA121 | SELL | MA365 | 80 | 41 | 97.6% | 0.64 |
| MA182 | SELL | MA365 | 60 | 32 | 93.8% | 0.52 |

Da qui derivano i **6 pattern dell'EA** (vedi §STATO CORRENTE in cima), filtrati tenendo solo
quelli con performance positiva anche out-of-sample. Tabella completa in `analisi_corretta_oos.txt`.


## 8. Risultati Completi delle Analisi

_(Sezione rimossa: descriveva la vecchia configurazione a 10 pattern exit-cross, non più attiva. Vedi **⭐ STATO CORRENTE (v2.05)** in cima per i 6 pattern attuali.)_

## 9. Architettura dell'EA

### 9.1 Struttura Generale del Codice

```mql5
// EA_Pattern.mq5 - PaPP v2.02
// Multi-Pattern EA: fino a 10 pattern configurabili da input MQL5
// Ogni pattern: Entry, Exit, SL, TP, Direction. Tutti in simultanea.
// Linee supportate: 0=Median, 3, 7, 14, 30, 121, 182, 365
// Dir: 0=OFF, 1=BUY, 2=SELL
```

L'EA è strutturato in blocchi funzionali:

```
OnInit()                     → Inizializzazione
OnTick()                     → Ciclo principale
  BuildCrossCache()          → Calcola crossover D1
  CheckPatternExits()        → Chiudi posizioni
  OpenPatternTrade()         → Apri nuove posizioni
CalcLotByDist()              → Position sizing
ReadBufD1()                  → Lettura dati D1
```

### 9.2 InitPatterns — Caricamento Pattern

```mql5
struct Pattern {
   int entry;     // Linea di entrata (0=Med, 3, 7, 14, 30, 121, 182, 365)
   int exit;      // Linea di uscita per cross (0=nessuna)
   int slLine;    // Linea per SL (0=nessuna)
   int tpPt;      // TP in punti (0=nessuno)
   int dir;       // Direzione: 0=OFF, 1=BUY, 2=SELL
};

Pattern g_patterns[MAX_PATTERNS];  // MAX_PATTERNS = 20
int g_numPatterns;
```

`InitPatterns()` popola l'array leggendo gli input InpP1_* .. InpP10_*. Per ogni pattern:

1. Se `dir = 0`, skippa (pattern disabilitato)
2. Valida che entry/exit/slLine siano periodi supportati
3. Se non validi, logga WARNING e skippa
4. Incrementa `g_numPatterns`

### 9.3 OnTick — Ciclo Principale

```mql5
void OnTick()
{
   // 1. Aspetta che l'indicatore sia pronto
   if(!WaitIndicator()) return;
   
   // 2. Nuova barra sul chart TF corrente
   if(!IsNewBar()) return;
   
   // 3. Controllo D1: elabora UNA volta al giorno
   datetime d1today = iTime(_Symbol, PERIOD_D1, 0);
   if(d1today == 0)             return;
   if(d1today == g_lastD1Today) return;  // già processata oggi
   g_lastD1Today = d1today;
   
   // 4. Ricalcola crossover
   BuildCrossCache();
   
   // 5. Esci dalle posizioni su exit-cross (TP/SL sono broker-side)
   CheckPatternExits();
   
   // 6. SL dinamico: trascina lo stop sulla linea MA (v2.05)
   UpdateDynamicSL();
   
   // 7. Controllo limite globale posizioni
   if(InpMaxPos > 0 && PositionsTotal() >= InpMaxPos) { ... return; }
   
   // 8. Apri nuove posizioni
   for(int pi = 0; pi < g_numPatterns; pi++)
      OpenPatternTrade(pi);
}
```

**Vincolo D1**: l'EA processa segnali UNA volta al giorno. Questo garantisce:

- Coerenza con l'analisi che ha generato i pattern (tutta su D1)
- Crossover basati su barre D1 COMPLETE (shift 1 e 2)
- Nessun falso segnale intraday

### 9.4 Cross Cache — BuildCrossCache

```mql5
void BuildCrossCache()
{
   for(int b = 0; b < 8; b++)   // 8 buffer = 8 linee
      g_crossCache[b] = CheckCrossD1(b);
}

int CheckCrossD1(int buf)
{
   double d1Close2 = iClose(_Symbol, PERIOD_D1, 2);  // 2 giorni fa
   double d1Close1 = iClose(_Symbol, PERIOD_D1, 1);  // 1 giorno fa
   if(d1Close2 <= 0.0 || d1Close1 <= 0.0) return 0;
   
   double ma2, ma1;
   if(!ReadBufD1(buf, 2, ma2)) return 0;  // MA di 2 giorni fa
   if(!ReadBufD1(buf, 1, ma1)) return 0;  // MA di 1 giorno fa
   
   // Bullish cross: close[i] > MA[i] E close[i-1] <= MA[i-1]
   if(d1Close1 > ma1 && d1Close2 <= ma2) return +1;
   // Bearish cross: close[i] < MA[i] E close[i-1] >= MA[i-1]
   if(d1Close1 < ma1 && d1Close2 >= ma2) return -1;
   
   return 0;  // Nessun crossover
}
```

Il cross cache evita ricalcoli ridondanti: tutti gli 8 crossover sono calcolati una sola volta per tick D1 e riusati da tutti i pattern.

### 9.5 ReadBufD1 — Lettura Dati D1

```mql5
bool ReadBufD1(int buf, int d1Shift, double &val)
{
   datetime d1Time = iTime(_Symbol, PERIOD_D1, d1Shift);
   if(d1Time == 0) return false;
   
   double tmp[1];
   
   // PERCORSO 1: Handle D1 diretto
   if(g_indD1 != INVALID_HANDLE)
   {
      int copied = CopyBuffer(g_indD1, buf, d1Shift, 1, tmp);
      if(copied == 1 && IsPriceOk(tmp[0]))
      {
         val = tmp[0];
         return true;
      }
   }
   
   // PERCORSO 2: Fallback sul chart TF
   int chartShift = iBarShift(_Symbol, _Period, d1Time, false);
   if(chartShift < 0) return false;
   if(CopyBuffer(g_ind, buf, chartShift, 1, tmp) != 1) return false;
   val = tmp[0];
   return IsPriceOk(val);
}
```

**Due percorsi di lettura**:

1. **Handle D1** (`g_indD1`): chiamata `iCustom` su `PERIOD_D1`. Lettura diretta dei buffer D1.
2. **Fallback chart TF**: converte il timestamp D1 nell'indice del chart TF corrente e legge da lì.

Se `g_indD1 == INVALID_HANDLE` (inizializzazione fallita), viene usato sempre il fallback. In questo caso il log mostra:

```
WARNING: g_indD1 fallito - usero' solo chart fallback
```

### 9.6 CheckPatternExits — Uscita Posizioni

```mql5
void CheckPatternExits()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol) continue;
      if(g_pos.Magic() != InpMagic) continue;
    
      ulong ticket = g_pos.Ticket();
      int pi = GetPatternIndex(ticket);  // Legge "P0".."P9" dal commento
      if(pi < 0 || pi >= g_numPatterns) continue;
    
      Pattern p = g_patterns[pi];
      ENUM_POSITION_TYPE posType = g_pos.PositionType();
      bool shouldClose = false;
    
      // Solo EXIT cross (se pattern.exit > 0). Lo SL NON è più gestito qui:
      // il vecchio blocco "SL cross" è stato rimosso (v2.05).
      if(p.exit > 0)
      {
         int exitCross = CachedCross(MAPeriodToBuf(p.exit));
         int needExit = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(exitCross == needExit)
            shouldClose = true;
      }
    
      if(shouldClose)
         g_trade.PositionClose(ticket);
   }
}
```

La funzione identifica il pattern dal commento (`P0`..`P9`) e chiude solo su **exit cross**
(per i pattern con `exit > 0`). Nella config attuale v2.05 **tutti i pattern hanno `exit=0`**,
quindi questa funzione non chiude nulla: le uscite avvengono via **TP broker-side** e via
**`UpdateDynamicSL()`** (SL dinamico trascinato sulla linea MA — vedi §9.8), allineato a
`simulate_trade` del miner.

### 9.8 UpdateDynamicSL — SL Dinamico sulla Linea

Chiamata ad ogni nuova barra D1 (dopo `CheckPatternExits`). Per ogni posizione con `slLine > 0`:
legge il valore corrente della MA (shift 1 = barra chiusa, niente look-ahead) e **trascina lo
stop broker-side** su quel valore con `PositionModify(ticket, lineVal, curTP)` (il TP è
preservato). Se la linea raggiunge il prezzo (entro lo stops level), chiude a mercato. Replica
fedelmente lo SL dinamico dell'analisi (`pattern_mining.simulate_trade`).

### 9.7 OpenPatternTrade — Apertura Posizioni

Flusso completo di `OpenPatternTrade(pi)`:

```
1. Leggi cross dell'entry line dal cache
   Se cross == 0 → return (nessun segnale)

2. Determina wantDir:
   dir=1 (BUY) e cross=+1 → wantDir = 1
   dir=2 (SELL) e cross=-1 → wantDir = -1
   Altrimenti → return

3. Controllo limite per-pattern (InpMaxPerPattern)
   Conta quante posizioni aperte hanno lo stesso pattern index
   Se >= InpMaxPerPattern → return

4. Spread check (InpMaxSpread)
   Se spread > InpMaxSpread → return

5. Calcola entry price (ask per BUY, bid per SELL)

6. Calcola TP se tpPt > 0
   BUY: entry + tpPt * point
   SELL: entry - tpPt * point

7. Calcola SL se slLine > 0 (HARD SL broker-side)
   Leggi valore SL line dal D1 shift 1
   BUY: slVal < entry → sl = slVal
   SELL: slVal > entry → sl = slVal
   Se SL non piazzabile → SKIP trade (return)

8. Calcola riskDist
   Se SL presente: riskDist = abs(entry - sl)
   Se solo TP: riskDist = tpPt * point
   Se nessuno: riskDist = pipSize * 1000 (virtuale)

9. Protezione distanza minima (InpMinSLDistPts)
   Se riskDist < InpMinSLDistPts * point → SKIP

10. Calcola lotto via CalcLotByDist(riskDist)
    Se lotto ≤ 0 → return

11. Apri posizione con PositionOpen()
    Commento: "P" + pi (es. "P3")
```

---

## 10. Pattern Dettagliati

_(Sezione rimossa: descriveva la vecchia configurazione a 10 pattern exit-cross, non più attiva. Vedi **⭐ STATO CORRENTE (v2.05)** in cima per i 6 pattern attuali.)_

## 11. Risk Management

### 11.1 Parametri Configurabili

| Input MQL5           | Default | Range      | Descrizione                                           |
| -------------------- | ------- | ---------- | ----------------------------------------------------- |
| `InpRiskPct`       | 1.0     | 0.1–10.0  | Percentuale di equity rischiata per trade             |
| `InpLotFixed`      | 0.0     | 0.0–100.0 | Lotto fisso (0 = usa rischio %)                       |
| `InpMaxLot`        | 0.0     | 0.0–100.0 | Lotto massimo assoluto (0 = usa limite broker)        |
| `InpMaxSpread`     | 50      | 0–500     | Spread massimo in punti per aprire (0 = disabilita)   |
| `InpMinSLDistPts`  | 50      | 10–1000   | Distanza minima SL in punti (protezione lotti enormi) |
| `InpMaxPos`        | 20      | 0–100     | Max posizioni totali (0 = illimitato)                 |
| `InpMaxPerPattern` | 1       | 0–10      | Max posizioni per pattern (0 = illimitato)            |

### 11.2 Position Sizing — CalcLotByDist

```mql5
double CalcLotByDist(double riskDist)
{
   // 1. Lotto fisso (sovrascrive rischio %)
   if(InpLotFixed > 0.0)
      return (InpMaxLot > 0.0) ? MathMin(InpLotFixed, InpMaxLot) : InpLotFixed;
   
   // 2. Calcolo risk-based
   double risk   = g_acc.Equity() * InpRiskPct / 100.0;
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double ticks    = riskDist / tickSize;
   double lotRaw   = risk / (ticks * tickVal);
   
   // 3. Arrotondamento e cap
   double lotStep  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot      = MathFloor(lotRaw / lotStep) * lotStep;
   double brokerMax = (InpMaxLot > 0.0) ? MathMin(maxLot, InpMaxLot) : maxLot;
   
   return MathMax(minLot, MathMin(lot, brokerMax));
}
```

**Esempio numerico**:

```
Equity: $10,000
InpRiskPct: 1.0% → rischio = $100
EURUSD: tickSize = 0.00001, tickVal = $10
riskDist = 0.0500 (500pt = 50 pip)

ticks = 0.0500 / 0.00001 = 5000
lotRaw = $100 / (5000 × $10) = $100 / $50,000 = 0.002
→ lotto = 0.01 (minimo)
```

Se riskDist fosse 0.0010 (10pt = 1 pip):

```
ticks = 0.0010 / 0.00001 = 100
lotRaw = $100 / (100 × $10) = $100 / $1,000 = 0.10
→ lotto = 0.10
```

Più riskDist è piccolo → più il lotto è grande. Ecco perché `InpMinSLDistPts` è essenziale.

### 11.3 Protezioni in Cascata (Prima dell'Apertura)

L'EA ha 6 controlli sequenziali prima di aprire una posizione:

```
1. Limite per-pattern (InpMaxPerPattern)
   → Salta se già N posizioni aperte per questo pattern

2. Limite globale (InpMaxPos)
   → Salta se PositionsTotal >= InpMaxPos

3. Spread check (InpMaxSpread)
   → Salta se ask-bid > InpMaxSpread

4. SL validità (se slLine > 0)
   → Salta se SL non piazzabile (lato sbagliato o lettura fallita)

5. Distanza minima (InpMinSLDistPts)
   → Salta se riskDist < InpMinSLDistPts

6. Lotto valido (> 0)
   → Salta se CalcLotByDist restituisce 0
```

### 11.4 Protezioni in Cascata (Dopo l'Apertura)

```
1. Hard SL broker-side
   → Stop-loss inviato al broker all'apertura (valore della SL line all'entry)
   → Protegge da gap intraday e disconnessioni
   → Attivo per tutti i pattern (tutti hanno slLine > 0)

2. SL dinamico — UpdateDynamicSL (v2.05)
   → A ogni chiusura D1 trascina lo stop broker-side sul valore corrente della MA
   → Se la linea raggiunge il prezzo, chiude a mercato
   → TP fisso broker-side preservato

3. Exit cross check — CheckPatternExits
   → Chiude se la exit line fa crossover avverso
   → Attivo solo per pattern con exit > 0 (nella config attuale: nessuno)
```

---

## 12. Guida all'Uso

### 12.1 Installazione

1. Copiare `EA/EA_Pattern.mq5` in `MetaTrader 5/MQL5/Experts/` (oppure il file direttamente dalla root `EA_Pattern.mq5`)
2. Copiare `Indicatori/PHAI_Median.ex5` in `MetaTrader 5/MQL5/Indicators/`
3. Aprire MetaEditor (F4), compilare l'EA (F7)
4. Trascinare `EA_Pattern` su un chart EURUSD (qualsiasi TF, raccomandato M30+)
5. Abilitare Algo Trading

### 12.2 Configurazione Iniziale

Per un primo test, lasciare tutti i default:

```
InpRiskPct       = 1.0     (1% di rischio per trade)
InpMaxLot        = 0.0     (usa limite broker)
InpMaxSpread     = 50      (max 50pt = 5 pip)
InpMinSLDistPts  = 50      (min 50pt distanza SL)
InpMaxPos        = 20      (max 20 posizioni totali)
InpMaxPerPattern = 1       (1 posizione per pattern)
InpMagic         = 20260623
InpLog           = true

P1: entry=3  exit=121 sl=0   tp=0   dir=2   (MA3 SELL → MA121)
P2: entry=7  exit=121 sl=0   tp=0   dir=2   (MA7 SELL → MA121)
P3: entry=14 exit=121 sl=0   tp=0   dir=2   (MA14 SELL → MA121)
P4: entry=30 exit=121 sl=0   tp=0   dir=2   (MA30 SELL → MA121)
P5: entry=365 exit=7  sl=0   tp=0   dir=2   (MA365 SELL → MA7)
P6: entry=121 exit=182 sl=0  tp=0   dir=1   (MA121 BUY → MA182)
P7: entry=365 exit=182 sl=0  tp=0   dir=1   (MA365 BUY → MA182)
P8: entry=365 exit=121 sl=0  tp=0   dir=1   (MA365 BUY → MA121)
P9: entry=30  exit=0   sl=365 tp=150 dir=1   (MA30 BUY → SL365 TP150)
P10: entry=7  exit=0   sl=365 tp=150 dir=2   (MA7 SELL → SL365 TP150)
```

### 12.3 Backtest

1. Selezionare EURUSD, timeframe D1
2. Impostare `InpLog = true`
3. Avviare backtest su tutto il periodo disponibile
4. Verificare nel log:
   ```
   INIT OK sym=EURUSD tf=PERIOD_D1 magic=20260623 risk=1.0% maxLot=0.00 maxSpread=50 minSL=50pt maxPos=20 maxPerPatt=1 patterns=10
   ```
5. Se il numero di pattern è < 10, controllare i WARNING:
   ```
   WARNING: Pattern X ... line ... invalida
   ```

### 12.4 Interpretazione del Log

```
=== SEGNALE === barra=2024.01.02 D1=2024.01.02 pos=3 patterns=10
```

→ Nuovo giorno D1. 3 posizioni aperte, 10 pattern attivi.

```
>>> CHIUSO [1] EXIT MA121 cross #12345678
```

→ Pattern 1 ha chiuso posizione perché MA121 ha fatto bullish cross.

```
>>> APERTURA [9] BUY lot=0.10 entry=1.10500 sl=1.09500 tp=1.10650 P9
```

→ Pattern 9 ha aperto BUY, lotto 0.10, entry 1.10500, SL a 1.09500, TP a 1.10650.

```
   Pattern 9 SKIPPED: SL line MA365 non piazzabile (lato sbagliato o lettura fallita)
```

→ MA365 sopra il prezzo per BUY → trade saltato.

```
   Pattern 4 SKIPPED: riskDist troppo piccolo (12.0pt < 50pt)
```

→ Distanza SL troppo piccola → trade saltato.

```
   Pattern 2 ha gia' 1 posizioni (max 1) - salto
```

→ Limite per-pattern raggiunto → non apre seconda posizione.

### 12.5 Ottimizzazione

Parametri da considerare per ottimizzazione in ordine di impatto:

1. **InpMinSLDistPts**: aumentare a 80–100 per ridurre frequenza trade P9/P10 (meno lotti enormi)
2. **InpMaxPerPattern**: 2 o 3 permette stacking (raddoppia esposizione per pattern)
3. **InpRiskPct**: ridurre a 0.5% per account piccoli, aumentare a 2–3% per aggressivo
4. **InpMaxLot**: 1.0 o 2.0 per cap esplicito

---

## 13. Walk-Forward Validation

### 13.1 Metodologia

Split temporale **train ≤ 2020.01.01 / test > 2020.01.01** (`--split-date=2020.01.01`).
I pattern sono selezionati SOLO sul training e validati sul test mai visto, con metodologia
corretta (Sharpe per-trade, no look-ahead, spread + commissione). Comando in §STATO CORRENTE.

### 13.2 Validazione dei 6 pattern dell'EA (train ≤2020 → test >2020)

| Pattern | Train (Win / Sh) | Test OOS (Win / PnL / Sh) |
| --- | --- | --- |
| MA30 SELL SL=MA365 TP=150 | 97% / 0.19 | **95% / +5113 / 1.96** |
| MA121 BUY SL=MA365 TP=150 | 93% / 0.36 | **89% / +2806 / 1.07** |
| MA365 SELL SL=MA121 TP=120 | 96% / 0.37 | 89% / +1070 / 0.38 |
| MA7 SELL SL=MA365 TP=120 | 94% / 0.15 | 93% / +4640 / 0.24 |
| MA30 BUY SL=MA365 TP=150 | 98% / 2.47 | 90% / +2964 / 0.23 |
| MA14 BUY SL=MA365 TP=150 | 94% / 0.22 | 94% / +5193 / 0.17 |

Tutti e 6 restano **positivi out-of-sample** (PnL > 0, win ~90%), con Sharpe per-trade modesto
(0.17–1.96). I pattern di Analisi 1/2 (cross-exit) e quelli con SL veloce / TP minuscolo
**crollano OOS** (win→~35% o Sharpe negativo) → esclusi. Dettagli in `analisi_corretta_oos.txt`.

## 14. Limitazioni e Rischi Noti

### 14.1 Dipendenza dall'Indicatore PHAI_Median.ex5

L'EA dipende dall'indicatore personalizzato per tutti i valori delle 8 linee. Se l'indicatore:

- Non è presente in `MQL5/Indicators/` → INIT_FAILED
- Ha un bug nei buffer oltre l'indice 1 → crossover errati
- Non calcola correttamente su D1 → fallback chart TF con possibili discrepanze

**Il fix del dead-code branch in PHAI_Median.OnCalculate() è ancora aperto.**

### 14.3 Gap Intraday

Tutti i 6 pattern attivi hanno un **hard SL broker-side** (al valore della SL line all'entry,
poi trascinato da `UpdateDynamicSL`), quindi il gap intraday è in gran parte coperto. Restano
rischiosi solo i gap che superano lo SL (es. SNB 2015, eventi macro estremi): in quel caso il
fill avviene oltre il livello di stop e la perdita può eccedere quella pianificata.

### 14.4 Accoppiamento tra Pattern

I pattern condividono le stesse MA/segnali, quindi possono entrare su movimenti correlati.
Config attuale: **3 SELL** (MA30, MA365, MA7) + **3 BUY** (MA121, MA30, MA14). Con
`InpMaxPerPattern = 1` ogni pattern apre 1 posizione, ma `InpMaxPos = 20` consente fino a 6
posizioni contemporanee (correlate per direzione) → rischio direzionale amplificato in trend forti.

### 14.5 Overfitting e Cambio di Regime

I pattern sono stati selezionati su EURUSD 2009–2026 (trend ribassista dominante). **Validati
out-of-sample** (train ≤2020, test >2020): tutti e 6 restano positivi, ma con Sharpe per-trade
modesto (0.17–1.96). Se il mercato cambia regime, le performance possono degradare. La
diversificazione 3 BUY / 3 SELL bilancia parzialmente la direzionalità.

### 14.6 Spread / Commissioni / Swap

Il miner corretto applica spread 15pt + commissione (`--commission`) + swap per barra (`--swap`).
Spread reali su EURUSD D1 sono tipicamente 10–20pt ma salgono a 50–100pt in illiquidità; l'EA
filtra con `InpMaxSpread` (default 50pt) all'apertura. I pattern a PnL medio basso soffrono di
più di costi alti. ⚠️ Lo **swap overnight** pesa sulle posizioni tenute a lungo: verificarlo coi
valori reali del broker.

### 14.7 Profilo Alto-Win / Perdita-Rara-Grande (tutti i 6 pattern)

Tutti i pattern usano SL=MA365 (o MA121) **lontano** + TP fisso vicino → Win Rate ~90% ma
perdita grande quando lo SL viene colpito. In un forte trend avverso (stop consecutivi), la
perdita cumulativa può essere significativa e concentrarsi in periodi di alta volatilità.
**Il position sizing (`InpRiskPct`) è la difesa principale**: dimensiona il lotto in base alla
distanza dello SL, così la perdita per trade resta controllata nonostante lo SL lontano.

---

## Appendice A: Glossario

| Termine                 | Definizione                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------- |
| **Punto (pt)**    | 0.00001 per EURUSD a 5 decimali. 10pt = 1 pip                                         |
| **Pip**           | 0.0001 per EURUSD. 1 pip = 10pt                                                       |
| **Tick**          | Movimento minimo del prezzo. Su EURUSD = 0.00001 = 1pt                                |
| **Tick Value**    | Valore monetario di un tick. Per 1 lotto standard EURUSD ≈ $10                       |
| **Crossover**     | Quando il prezzo CHIUDE oltre una MA dopo aver chiuso dall'altro lato il giorno prima |
| **Bullish cross** | D1 close > MA (dopo essere stato ≤ MA)                                               |
| **Bearish cross** | D1 close < MA (dopo essere stato ≥ MA)                                               |
| **Sharpe (per-trade)** | (Avg PnL) / (Std PnL), **non** annualizzato. >1 già molto buono per strategia sporadica |
| **Profit Factor** | Somma profitti /                                                                      |
| **SL dinamico**   | SL che segue il valore corrente della linea (es. MA365)                               |
| **Hard SL**       | Stop-loss broker-side inviato all'apertura                                            |
| **Floating SL**   | SL che non è un ordine fermo ma viene controllato a ogni barra                       |
| **Risk-% sizing** | Calcolo lotto:`(equity × Risk%) / (riskDist × tickValue / tickSize)`              |
| **Walk-forward**  | Training su 70% dati, validation su 30% non visti dal training                        |

## Appendice B: Codice Colore nel Log

| Messaggio               | Significato                            |
| ----------------------- | -------------------------------------- |
| `=== SEGNALE ===`     | Inizio elaborazione giornaliera        |
| `>>> APERTURA [N]`    | Nuova posizione aperta per pattern N   |
| `>>> CHIUSO [N]`      | Posizione chiusa per pattern N         |
| `SKIPPED: SL line`    | Trade saltato (SL non piazzabile)      |
| `SKIPPED: riskDist`   | Trade saltato (distanza minima)        |
| `ha gia' N posizioni` | Limite per-pattern raggiunto           |
| `WARNING:`            | Non bloccante (es. linea invalida)     |
| `FATAL:`              | Bloccante (es. indicatore non trovato) |
| `ERR entrata`         | Errore broker all'apertura (retcode)   |

## Appendice C: Lista Completa dei File

| File | Path nel repo | Descrizione |
| --- | --- | --- |
| `PHAI_Median.mq5` (+.ex5) | `Motore base _linea-prezzo/Indicatore/` | indicatore (7 MA + mediana, D1) |
| `Export_PAPP.mq5` (+.ex5) | `Motore base _linea-prezzo/Indicatore/` | script esportazione CSV |
| `pattern_mining.py` | `Motore base _linea-prezzo/Indicatore/` | miner (analisi/validazione) |
| `EA_<SIMBOLO>.mq5` (+.ex5) | `Motore base _linea-prezzo/<SIMBOLO>/` | EA coi pattern del simbolo |
| `PAPP_Export*.csv` | `Motore base _linea-prezzo/<SIMBOLO>/` | dataset D1 del simbolo |
| `analisi_oos.txt` | `Motore base _linea-prezzo/<SIMBOLO>/` | report del miner |
| `INDICATORE_/EXPORT_/MINER_*.md` | `Motore base _linea-prezzo/Indicatore/` | doc per-componente |
| `DOCUMENTAZIONE.md`, `MAPPA_FILE.md` | `docs/` | questo documento + mappa file |

## Appendice D: Sequenza Completa dei Comandi

```bash
# 1. Esportare i dati (da MetaTrader 5): eseguire Export_PAPP su <SIMBOLO> D1
#    Output: <DATI_MT5>\MQL5\Files\PAPP_Export.csv

# 2. Copiare il CSV nella cartella del simbolo
cp "<DATI_MT5>/MQL5/Files/PAPP_Export.csv" "Motore base _linea-prezzo/<SIMBOLO>/"

# 3. Analisi con walk-forward + costi (dalla cartella del simbolo)
cd "Motore base _linea-prezzo/<SIMBOLO>"
python3 "../Indicatore/pattern_mining.py" PAPP_Export.csv \
        --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt

# 4. Variante walk-forward a finestre multiple
python3 "../Indicatore/pattern_mining.py" PAPP_Export.csv --robust --folds=5 --spread=15 --commission=7

# 5. Copiare EA e indicatore su MT5, compilare in MetaEditor (F7), attaccare al grafico
```
