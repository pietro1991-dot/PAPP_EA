# PAPP_EA — Documentazione Completa

## Indice

1. [Visione d'Insieme](#1-visione-dinsieme)
2. [Pipeline dei Dati](#2-pipeline-dei-dati)
3. [Il Dataset: PAPP_Export.csv](#3-il-dataset-papp_exportcsv)
4. [Pattern Mining — Le Tre Analisi](#4-pattern-mining--le-tre-analisi)
5. [Analisi 1: Crossover → Qualsiasi Crossover Opposto](#5-analisi-1-crossover--qualsiasi-crossover-opposto)
6. [Analisi 2: Crossover → Crossover su Linea Specifica](#6-analisi-2-crossover--crossover-su-linea-specifica)
7. [Analisi 3: Grid Search SL Dinamico + TP Fisso](#7-analisi-3-grid-search-sl-dinamico--tp-fisso)
8. [Risultati Completi delle Analisi](#8-risultati-completi-delle-analisi)
9. [Architettura dell'EA](#9-architettura-dellea)
10. [Pattern Dettagliati](#10-pattern-dettagliati)
11. [Risk Management](#11-risk-management)
12. [Guida all'Uso](#12-guida-alluso)
13. [Walk-Forward Validation](#13-walk-forward-validation)
14. [Limitazioni e Rischi Noti](#14-limitazioni-e-rischi-noti)

---

## 1. Visione d'Insieme

PAPP_EA è un sistema di trading algoritmico per MetaTrader 5 basato su **crossover di medie mobili calcolate su timeframe giornaliero (D1)**. Utilizza l'indicatore personalizzato `PaPP_Median.ex5` che analizza 8 linee sul prezzo EURUSD:

| Linea | Periodo | Nome nel codice | Descrizione |
|-------|---------|-----------------|-------------|
| **Median** | 0 | `BUF_MEDIAN` (0) | Mediana del prezzo D1 (valore centrale del range giornaliero) |
| **MA3** | 3 | `BUF_MA3` (7) | Media mobile semplice a 3 giorni |
| **MA7** | 7 | `BUF_MA7` (6) | Media mobile semplice a 7 giorni (~1 settimana) |
| **MA14** | 14 | `BUF_MA14` (5) | Media mobile semplice a 14 giorni (~2 settimane) |
| **MA30** | 30 | `BUF_MA30` (4) | Media mobile semplice a 30 giorni (~1 mese) |
| **MA121** | 121 | `BUF_MA121` (3) | Media mobile semplice a 121 giorni (~6 mesi) |
| **MA182** | 182 | `BUF_MA182` (2) | Media mobile semplice a 182 giorni (~9 mesi) |
| **MA365** | 365 | `BUF_MA365` (1) | Media mobile semplice a 365 giorni (~1 anno) |

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

1. Si connette all'indicatore `PaPP_Median.ex5` su EURUSD D1
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

| Metrica | Formula SQL | Implementazione Python |
|---------|-------------|----------------------|
| **Sharpe Ratio** | `AVG(pnl) / STDEV(pnl) × SQRT(252)` | `mean(pnls) / stdev(pnls) * sqrt(252)`. Se std=0: 99 se avg>0, −99 se avg<0 |
| **Win Rate** | `COUNT(pnl>0) / COUNT(*) × 100` | Percentuale trade positivi |
| **Profit Factor** | `SUM(pnl>0) / ABS(SUM(pnl<0))` | `sum(pos) / max(1, abs(sum(neg)))` |
| **Avg PnL** | `AVG(pnl)` | Media in punti. Positivo = profittevole |
| **Total PnL** | `SUM(pnl)` | Profitto netto totale in punti |
| **Avg Bars** | `AVG(bars_held)` | Durata media in giorni D1 |

**Nota sullo Sharpe**: lo Sharpe ratio qui è CRUDO — non usa il risk-free rate, non è differenziato per punti. Un Sharpe > 1.0 è considerato buono, > 2.0 ottimo, > 3.0 eccellente. I pattern con Sharpe 99.0 sono artefatti statistici (tutti i trade hanno lo stesso PnL, std=0) e andrebbero ignorati.

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

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `crossMA_X` | int {−1, 0, +1} | +1 = prezzo chiude sopra MA (bullish cross). −1 = prezzo chiude sotto MA (bearish cross). 0 = nessun crossover |
| `dX%` | float | Distanza percentuale: `(close − MA_X) / close × 100`. Positivo = prezzo sopra MA |
| `aX` | int {0, 1} | 1 = prezzo sopra MA (above). 0 = prezzo sotto MA (below) |
| `longBelow` | int {0, 1} | 1 = prezzo sotto la maggior parte delle MA lunghe (contesto ribassista) |
| `longAbove` | int {0, 1} | 1 = prezzo sopra la maggior parte delle MA lunghe (contesto rialzista) |
| `cluster%` | float | Quanto le MA sono raggruppate (basso = allineate, alto = disperse) |
| `vel%` | float | Velocità di movimento del prezzo rispetto alla media storica |
| `vol%` | float | Volume relativo (rispetto alla media) |
| `orderScore` | int | Allineamento delle MA (valore alto = forte trend) |
| `MA3_7` | float | Distanza in punti tra MA3 e MA7 (espansione/contrazione) |

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

### 5.2 Esempio concreto (dal dataset)

```
2010.01.04: close=1.44111, MA7=1.43596
  crossMA7 = +1 (bullish: close > MA7, giorno prima close[−1] ≤ MA7[−1])
  → Apre BUY a 1.44111

2010.01.05: close=1.43624, MA7=1.43577
  crossMA7 = 0 (nessun crossover)
  crossMA3 = −1 (bearish: close < MA3)
  → Chiude BUY al primo cross opposto su MA3
  PnL = (1.43624 − 1.44111) / 0.00001 − 15spread = −502pt
```

### 5.3 Tabella Risultati Completa

```
entry_line    dir     Trades    Win%    AvgPts   Sharpe   ProfitF    TotPnl   AvgBars
MA182        SELL       94    43.6%    +84.3     1.43      1.30     +7921      2.1
MA365        SELL       60    36.7%    +61.0     1.02      1.22     +3659      2.1
MA7          SELL      558    36.7%    +20.2     0.39      1.07    +11250      2.0
MA14         SELL      372    37.9%     +0.8     0.02      1.00      +303      2.0
MA121         BUY      121    35.5%     −1.4    −0.02      1.00      −164      1.9
MA121        SELL      121    30.6%     −9.7    −0.19      0.96     −1169      2.0
MA3          SELL     1091    35.0%    −10.7    −0.20      0.96    −11628      1.9
MA30         SELL      253    33.6%    −20.5    −0.41      0.93     −5181      1.9
MA14          BUY      371    35.0%    −30.1    −0.58      0.90    −11182      2.0
Median       SELL      435    33.6%    −30.2    −0.62      0.89    −13127      1.9
MA3           BUY     1091    35.2%    −36.5    −0.69      0.88    −39806      2.0
MA7           BUY      558    35.1%    −41.5    −0.80      0.87    −23154      1.9
Median        BUY      435    33.6%    −66.3    −1.23      0.80    −28833      1.9
MA30          BUY      253    29.6%    −77.2    −1.38      0.76    −19526      1.9
MA365         BUY       59    37.3%    −70.2    −1.60      0.76     −4140      1.9
```

### 5.4 Interpretazione

**Pattern profittevoli** (Sharpe > 0):
- **MA182 SELL**: Sharpe 1.43, +84.3pt medio. Il miglior pattern Analisi 1.
- **MA365 SELL**: Sharpe 1.02, +61.0pt medio. Pochi trade (60) ma profittevoli.
- **MA7 SELL**: Sharpe 0.39, +20.2pt medio. Molti trade (558), profitto per accumulo.
- **MA14 SELL**: Sharpe 0.02, +0.8pt medio. Sostanzialmente in pareggio.

**Pattern non profittevoli** (Sharpe < 0):
- **MA3 BUY**: Sharpe −0.69, −36.5pt medio, ha PERSO −39.806pt totali. Peggior pattern.
- **Tutti i BUY** tranne MA121 hanno Sharpe negativo.

**Osservazioni chiave**:
1. I pattern **SELL dominano i BUY** in Analisi 1. Questo riflette il trend di lungo periodo dell'EURUSD (discesa da 1.60 a 1.04 in 17 anni).
2. Usare "qualsiasi cross opposto" come exit produce trade **brevissimi** (media 2 barre). Il più lungo dura poche barre.
3. Lo Sharpe massimo è 1.43 (MA182 SELL) — non eccellente, ma positivo.
4. I pattern con Sharpe negativo vengono **scartati** dalla selezione finale. Nessuno di questi è usato nell'EA.

**Perché Analisi 1 non viene usata direttamente nell'EA?**
Perché l'exit "primo cross opposto su qualsiasi linea" è troppo reattiva. Un piccolo movimento contrario su MA3 chiude una posizione che avrebbe potuto essere profittevole se lasciata aperta. L'Analisi 2 risolve questo problema.

---

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

### 6.2 Esempio concreto

```
Entry: MA3 SELL (crossMA3 = −1) @ 1.44111
Exit su: MA121 (crossMA121 = +1 = bullish)

Il trade rimane aperto FINCHÉ MA121 non fa un bullish cross.
MA3, MA7, MA14, MA30, MA182, MA365, Median possono fare
centinaia di crossover contrari — la posizione NON viene chiusa.
Solo MA121 che fa bullish cross chiude.
```

### 6.3 Tabella Risultati Completa (Top 25)

```
entry_line  dir   exit_line      Trades    Win%    AvgPts    Sharpe   ProfitF     TotPnl   AvgBars
MA365       SELL  crossMA7          60    45.0%   +241.6     3.35      1.85    +14496      4.6
MA30        SELL  crossMA121       245    43.3%   +633.3     2.64      1.72   +155169     41.1
MA365       SELL  crossMA14         60    48.3%   +222.5     2.61      1.65    +13352      8.6
MA121        BUY  crossMA182       118    39.8%   +393.6     2.20      1.59    +46450     38.8
MA7         SELL  crossMA121       544    46.7%   +532.7     2.09      1.53   +289775     45.2
MA3         SELL  crossMA121      1060    45.7%   +552.3     2.07      1.52   +585409     46.9
MA30        SELL  crossMA14        252    39.7%   +207.3     1.70      1.42    +52251      8.1
MA14        SELL  crossMA121       363    43.8%   +390.8     1.61      1.39   +141874     42.6
MA365       SELL  crossMed          60    41.7%   +173.4     1.57      1.46    +10407     10.6
MA365        BUY  crossMA182        55    41.8%   +286.9     1.51      1.33    +15779     46.5
MA182       SELL  crossMA3          94    43.6%    +84.3     1.43      1.30     +7921      2.1
MA30        SELL  crossMA7         252    39.3%   +112.2     1.22      1.28    +28262      5.0
MA30        SELL  crossMed         252    33.3%   +134.1     1.18      1.32    +33786      7.7
MA365        BUY  crossMA121        56    50.0%   +188.7     1.08      1.22    +10568     46.9
MA365       SELL  crossMA3          60    36.7%    +61.0     1.02      1.22     +3659      2.1
MA182       SELL  crossMA14         94    45.7%    +94.3     0.84      1.18     +8865      9.1
MA7         SELL  crossMed         557    41.5%    +89.4     0.77      1.18    +49796      9.6
Median      SELL  crossMA121       426    38.7%   +147.6     0.69      1.15    +62888     35.4
MA7         SELL  crossMA3         558    37.3%    +23.9     0.46      1.09    +13332      2.0
Median      SELL  crossMA14        434    38.7%    +49.3     0.45      1.10    +21410      8.0
MA3         SELL  crossMA7        1089    39.1%    +32.6     0.38      1.08    +35496      5.2
MA182       SELL  crossMA7          94    48.9%    +27.1     0.35      1.07     +2548      4.8
Median      SELL  crossMA7         434    38.2%    +26.1     0.33      1.06    +11326      4.7
MA3         SELL  crossMed        1090    40.8%    +38.8     0.33      1.07    +42345     10.3
MA7         SELL  crossMA14        557    36.6%    +34.3     0.32      1.07    +19115      7.8
```

### 6.4 Analisi dei Migliori Pattern

**1. MA365 SELL → crossMA7** (Sharpe 3.35, 60 trade, +241.6pt medio)

Entra quando il prezzo rompe al ribasso la MA365 (bear market signal). Esce al primo rimbalzo settimanale (MA7 bullish cross). Trade brevi (4.6 barre), profitto alto. Pochi segnali (~3.5/anno) perché la MA365 viene attraversata raramente.

**2. MA30 SELL → crossMA121** (Sharpe 2.64, 245 trade, +633.3pt medio)

Entra su debolezza mensile (MA30 bearish cross), esce quando il trend semestrale (MA121) gira rialzista. **È il pattern con il PnL medio più alto** nella classe SELL. Trade lunghi (41 barre = ~2 mesi). Molto profitto per trade ma lunga esposizione.

**3. MA3 SELL → crossMA121** (Sharpe 2.07, 1060 trade, +552.3pt medio)

Entra su debolezza a 3 giorni, esce su inversione a 6 mesi. **Miglior rapporto trade/Sharpe**: 1060 trade in 17 anni (~62/anno) con Sharpe 2.07. PnL totale +585.409pt. È il pattern più robusto dell'intera analisi.

**4. MA7 SELL → crossMA121** (Sharpe 2.09, 544 trade, +532.7pt medio)

Simile a MA3→MA121 ma con ~metà dei trade. Sharpe leggermente superiore. Trade lunghi (45 barre).

### 6.5 Perché MA121 come Exit è Così Efficace?

MA121 è la media mobile a 121 giorni (~6 mesi). Quando il prezzo fa un bullish cross su MA121 in un downtrend, segnala un cambiamento di trend significativo a medio termine. Usare MA121 come exit significa:

- **Ignorare** i falsi rimbalzi su MA3/MA7/MA14 (rumore a breve termine)
- **Resistere** alle correzioni intermedie su MA30 (normali in un trend)
- **Uscire solo** quando il trend di 6 mesi si inverte

Questa combinazione (entry corta, exit lunga) cattura trend ribassisti di medio periodo filtrando il rumore.

### 6.6 Pattern Selezionati per l'EA (P1–P8)

Dall'Analisi 2 sono stati selezionati 8 pattern per l'EA:

| Pattern | Entry | Dir | Exit | Sharpe | Trades | AvgPts | AvgBars | Motivo Selezione |
|---------|-------|-----|------|--------|--------|--------|---------|------------------|
| P1 | MA3 | SELL | MA121 | 2.07 | 1060 | +552 | 47gg | Massimo trade, Sharpe eccellente |
| P2 | MA7 | SELL | MA121 | 2.09 | 544 | +533 | 45gg | Sharpe leggermente > P1 |
| P3 | MA14 | SELL | MA121 | 1.61 | 363 | +391 | 43gg | Complementare a P1/P2 |
| P4 | MA30 | SELL | MA121 | 2.64 | 245 | +633 | 41gg | Sharpe più alto del gruppo SELL |
| P5 | MA365 | SELL | MA7 | 3.35 | 60 | +242 | 5gg | Sharpe massimo, inversione veloce |
| P6 | MA121 | BUY | MA182 | 2.20 | 118 | +394 | 39gg | Miglior BUY |
| P7 | MA365 | BUY | MA182 | 1.51 | 55 | +287 | 47gg | BUY su trend annuale |
| P8 | MA365 | BUY | MA121 | 1.08 | 56 | +189 | 47gg | BUY alternativo |

**Criteri di selezione**:
1. Sharpe ratio > 1.0
2. Almeno 50 trade (significatività statistica)
3. Diversificazione: copertura di diverse linee di entrata
4. Bilanciamento BUY/SELL: 6 SELL, 3 BUY (la selezione include 2 BUY extra oltre P6–P8)

---

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

### 7.2 Esempio concreto

```
Data: 2010.01.04
Entry: MA7 BUY @ 1.44111 (crossMA7 = +1)
SL: MA365 = 1.39455 (465pt sotto = 46.5 pip sotto)
TP: 60pt (6 pips sopra)

Barra 2 (2010.01.05):
  high = 1.44830, low = 1.43467
  MA365 = 1.39483 (leggermente salita)
  Prezzo tocca TP? high >= 1.44111 + 0.00060 = 1.44171? SÌ! (1.44830)
  
  → TP colpito, PnL = 60 − 15(spread) = +45pt
  Trade chiuso in 1 barra = 1 giorno
```

### 7.3 Tabella Risultati Completa (Top 30)

```
entry_line  dir   sl_line  tp_pt  Trades    Win%    AvgPts   Sharpe   ProfitF    TotPnl   AvgBars
MA121       SELL  MA365     80       53    98.1%     +57.3    16.28      9.88    +3038      1.3
MA121       SELL  MA365     60       53    98.1%     +37.7    11.26      6.84    +1998      1.3
MA30         BUY  MA365    150      111    93.7%     +98.9     8.77      4.58   +10974      1.7
MA121       SELL  MA365     50       53    98.1%     +27.9     8.55      5.32    +1478      1.3
MA121        BUY  MA365    150       70    91.4%     +90.2     8.28      3.72    +6317      1.4
MA182       SELL  MA365     60       44    90.9%     +27.2     6.86      2.98    +1196      1.0
MA365       SELL  MA121    120       42    92.9%     +66.0     6.49      3.10    +2774      2.0
MA30         BUY  MA365    120      111    93.7%     +70.8     6.48      3.56    +7854      1.6
MA121        BUY  MA365    120       70    91.4%     +62.8     6.01      2.89    +4397      1.4
MA121       SELL  MA365     40       53    98.1%     +18.1     5.69      3.80     +958      1.1
MA121        BUY  MA365     80       70    92.9%     +39.5     5.52      2.89    +2764      1.1
MA30        SELL  MA365    150      139    96.4%     +90.0     4.97      3.24   +12504      2.3
MA30         BUY  MA365    100      111    93.7%     +52.0     4.87      2.88    +5774      1.6
MA365       SELL  MA121    100       42    92.9%     +47.5     4.80      2.51    +1994      1.8
MA182       SELL  MA365     50       44    90.9%     +18.1     4.77      2.32     +796      1.0
MA121        BUY  MA365    100       70    91.4%     +44.5     4.39      2.34    +3117      1.2
MA14        SELL  MA365     30      192    97.9%      +9.0     3.47      2.60    +1735      1.3
MA30        SELL  MA365    120      139    96.4%     +61.0     3.43      2.52    +8484      2.0
MA365       SELL  MA121     60       42    95.2%     +25.0     3.42      2.40    +1050      1.7
MA14         BUY  MA365    150      176    93.8%     +69.4     3.40      2.21   +12209      2.7
MA30         BUY  MA365     80      111    93.7%     +33.3     3.18      2.20    +3694      1.4
MA7         SELL  MA365    120      291    93.8%     +55.2     3.09      2.27   +16053      2.1
MA121        BUY  MA365     60       70    92.9%     +20.9     3.03      2.00    +1464      1.1
MA365       SELL  MA121     80       42    92.9%     +28.9     3.01      1.92    +1214      1.8
MA7         SELL  MA365    150      291    93.5%     +69.5     2.98      2.23   +20229      2.4
MA30         BUY  MA365     50      111    94.6%     +17.5     2.85      2.12    +1938      1.1
MA121       SELL  MA365     30       53    98.1%      +8.3     2.68      2.28     +438      1.0
MA182       SELL  MA365    100       44    88.6%     +34.4     2.67      1.84    +1512      1.1
MA7         SELL  MA365     80      291    94.5%     +32.3     2.62      2.11    +9406      1.9
MA30        SELL  MA365     60      139    97.8%     +28.1     2.61      2.77    +3910      1.6
```

### 7.4 Miglior SL Linea (Aggregata)

```
SL linea    PnL medio   Win%     Sharpe    Trade totali
MA365         +0.6pt    91.7%     0.03      27.486
MA121        −48.6pt    81.5%    −2.22      28.773
MA30         −97.4pt    64.7%    −4.88      32.202
MA14        −118.4pt    57.8%    −6.50      35.469
Median       −92.9pt    54.0%    −4.96      39.861
```

**MA365 è l'unica SL linea profittevole in media**. Ha Win% 91.7%, il che significa che il 91.7% dei trade con SL=MA365 termina a TP, non a SL. Questo perché MA365 è talmente lontana dal prezzo (in media) che il TP viene colpito prima.

MA14 e MA30 come SL sono distruttive: Sharpe −4.88 e −6.50. Queste linee sono troppo vicine al prezzo e vengono colpite frequentemente.

### 7.5 Miglior TP (Aggregato)

```
TP       PnL medio   Win%     Sharpe    Trade totali
150pt     −53.9pt    66.1%    −2.08      18.199
120pt     −62.7pt    66.7%    −2.62      18.199
100pt     −67.2pt    67.2%    −3.12      18.199
 80pt     −74.0pt    67.8%    −3.63      18.199
 60pt     −79.7pt    68.4%    −4.23      18.199
 50pt     −81.4pt    68.8%    −4.54      18.199
 40pt     −85.0pt    69.1%    −4.89      18.199
 30pt     −87.7pt    69.3%    −5.32      18.199
 20pt     −91.0pt    69.6%    −5.76      18.199
```

**TP 150pt è il migliore** tra i candidati (Sharpe −2.08, il meno peggio). Più il TP è piccolo, più viene colpito da SL prima di raggiungerlo. Questa tabella include TUTTI i pattern (anche quelli con SL vicina). I pattern migliori (SL=MA365 + TP=150pt) hanno Sharpe positivo.

### 7.6 Pattern Selezionati per l'EA (P9–P10)

| Pattern | Entry | Dir | SL | TP | Sharpe | Trades | Win% | AvgPts |
|---------|-------|-----|-----|-----|--------|--------|------|--------|
| **P9** | MA30 | BUY | MA365 | 150pt | 8.77 | 111 | 93.7% | +98.9pt |
| **P10** | MA7 | SELL | MA365 | 150pt | — | 291 | 93.5% | +69.5pt |

**Perché P9 e non altri?** P9 (MA30 BUY → MA365 SL + TP150) ha Sharpe 8.77, il più alto tra i pattern con SL=MA365 e un numero significativo di trade (>100). MA30 come entry fornisce un buon bilanciamento tra frequenza di segnale e qualità.

P10 è mirror speculare: MA7 SELL con SL=MA365 e TP=150. I dati per MA7 SELL → MA365 con TP150 mostrano Sharpe 2.98 (non nella top 30 ma comunque molto buono).

**Perché non MA121 SELL → MA365?** Ha Sharpe 16.28 ma solo 53 trade in 17 anni (~3/anno). Troppo pochi per essere affidabile in futuro.

**Nota importante su Sharpe 99.0**: I pattern che appaiono con Sharpe 99.0 nel summary sono artefatti: tutti i trade hanno PnL identico (+5pt, TP=20 colpito sempre prima dello SL), quindi std=0 e Sharpe=99. Non sono pattern reali e vengono ignorati nella selezione.

---

## 8. Risultati Completi delle Analisi

### 8.1 Riepilogo per Linea di Entrata (Miglior Pattern per Ogni Linea)

```
MA365  → SELL | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=38
MA182  → BUY  | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=54
MA121  → BUY  | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=68
MA30   → BUY  | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=139
MA14   → SELL | exit=TP  SL=MA30  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=139
MA7    → BUY  | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=156
MA3    → BUY  | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=314
Median → BUY  | exit=TP  SL=MA14  TP=20     Sharpe=99.00* | Win=100% | Avg=+5pt  | N=167
```
*Sharpe 99.0 = artefatto (std=0, tutti trade = +5pt TP=20 colpito sempre)

I veri pattern migliori (escludendo artefatti) sono i 10 selezionati per l'EA.

### 8.2 Tabella Riepilogo Completa (Tutti i 10 Pattern EA)

```
    Pattern     Entry   Dir   Exit/SL       TP    Sharpe   Trades    Win%    AvgPts    AvgBars
 ─────────────────────────────────────────────────────────────────────────────────────────────
 P1  MA3→MA121    MA3  SELL  MA121 cross    0      2.07     1060    45.7%   +552.3pt    47gg
 P2  MA7→MA121    MA7  SELL  MA121 cross    0      2.09      544    46.7%   +532.7pt    45gg
 P3  MA14→MA121  MA14  SELL  MA121 cross    0      1.61      363    43.8%   +390.8pt    43gg
 P4  MA30→MA121  MA30  SELL  MA121 cross    0      2.64      245    43.3%   +633.3pt    41gg
 P5  MA365→MA7  MA365  SELL    MA7 cross    0      3.35       60    45.0%   +241.6pt     5gg
 P6  MA121→MA182 MA121   BUY  MA182 cross    0      2.20      118    39.8%   +393.6pt    39gg
 P7  MA365→MA182 MA365   BUY  MA182 cross    0      1.51       55    41.8%   +286.9pt    47gg
 P8  MA365→MA121 MA365   BUY  MA121 cross    0      1.08       56    50.0%   +188.7pt    47gg
 P9  MA30+SL365  MA30   BUY  SL=MA365      150     8.77      111    93.7%    +98.9pt     2gg
 P10 MA7+SL365    MA7  SELL  SL=MA365      150     2.98      291    93.5%    +69.5pt     2gg
```

---

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
   
   // 5. Esci dalle posizioni
   CheckPatternExits();
   
   // 6. Controllo limite globale posizioni
   if(InpMaxPos > 0 && PositionsTotal() >= InpMaxPos) { ... return; }
   
   // 7. Apri nuove posizioni
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
      
      // 1. EXIT cross check (se pattern.exit > 0)
      if(p.exit > 0)
      {
         int exitCross = CachedCross(MAPeriodToBuf(p.exit));
         int needExit = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(exitCross == needExit)
            shouldClose = true;
      }
      
      // 2. SL cross check (se pattern.slLine > 0 e non già in exit)
      if(!shouldClose && p.slLine > 0)
      {
         int slCross = CachedCross(MAPeriodToBuf(p.slLine));
         int needSL = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(slCross == needSL)
            shouldClose = true;
      }
      
      if(shouldClose)
         g_trade.PositionClose(ticket);
   }
}
```

La funzione identifica il pattern associato a ogni posizione tramite il commento (`P0`..`P9`), poi verifica:
- **Exit cross** (per pattern con exit line): il cross opposto sulla linea d'exit
- **SL cross** (per pattern con SL line): il cross avverso sulla linea SL

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

### 10.1 Pattern 1: MA3 SELL → MA121 cross (P1)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA3 (3 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 2.07 |
| Trade totali | 1060 |
| Win Rate | 45.7% |
| PnL medio | +552.3pt |
| Tenuta media | 47 giorni |

**Entry**: il prezzo D1 chiude SOTTO MA3 dopo aver chiuso SOPRA o UGUALE a MA3 il giorno prima (crossover bearish). Questo è il primo segnale di debolezza a brevissimo termine. MA3 è la più reattiva delle 8 linee e genera 2183 segnali totali in 17 anni.

**Exit**: il prezzo D1 chiude SOPRA MA121 dopo aver chiuso SOTTO o UGUALE a MA121 (crossover bullish). L'exit richiede un'inversione del trend semestrale.

**Meccanismo**: la differenza di scala temporale tra entry (3gg) e exit (121gg) è il cuore del pattern. Si vende sul primo segnale debole e si resiste a tutti i rimbalzi intermedi fino a quando il trend di 6 mesi non inverte. I rimbalzi su MA3/MA7/MA14 vengono ignorati — solo MA121 conta.

**Esempio storico** (ricostruito dai dati):
```
2014.05.08: close=1.3720, MA3=1.3780 → crossMA3 = -1 (bearish)
  → Entra SELL a 1.3720
  ... 47 giorni di tenuta, prezzo scende a 1.3500, risale, scende ancora ...
2014.06.25: close=1.3620, MA121=1.3610 → crossMA121 = +1 (bullish)
  → Esce a 1.3620
  PnL = (1.3720 - 1.3620) / 0.00001 - 15 = +985pt
```

**Quando funziona**: trend ribassisti strutturati con correzioni intermedie che non rompono MA121.

**Quando fallisce**: mercati laterali dove MA3 e MA121 sono vicine — falsi segnali e uscite premature o in perdita.

**Rischio specifico**: nessun hard SL. La posizione rimane aperta fino al cross di MA121. In un gap down improvviso (es. Brexit, SNB), la perdita può essere grande prima che MA121 possa fare cross.

---

### 10.2 Pattern 2: MA7 SELL → MA121 cross (P2)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA7 (7 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 2.09 |
| Trade totali | 544 |
| Win Rate | 46.7% |
| PnL medio | +532.7pt |
| Tenuta media | 45 giorni |

**Entry**: prezzo D1 chiude sotto MA7 (crossover bearish). MA7 è meno reattiva di MA3 ma più di MA14.

**Exit**: prezzo D1 chiude sopra MA121 (crossover bullish). Stessa exit di P1.

**Differenza da P1**: P2 ha la metà dei trade (544 vs 1060) perché MA7 filtra parte del rumore che MA3 cattura. Lo Sharpe è leggermente superiore (2.09 vs 2.07). Il PnL medio è simile (~533pt vs ~552pt).

**Quando usare P2 invece di P1**: se si vuole ridurre il numero di posizioni aperte senza sacrificare Sharpe. P2 è più selettivo di P1.

---

### 10.3 Pattern 3: MA14 SELL → MA121 cross (P3)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA14 (14 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 1.61 |
| Trade totali | 363 |
| Win Rate | 43.8% |
| PnL medio | +390.8pt |
| Tenuta media | 43 giorni |

**Entry**: prezzo D1 chiude sotto MA14 (crossover bearish). Richiede 2 settimane di debolezza.

**Exit**: prezzo D1 chiude sopra MA121 (crossover bullish).

**Differenza da P1/P2**: Sharpe inferiore (1.61) e PnL medio più basso (+391pt). MA14 è una via di mezzo: non cattura i trend veloci come MA3, ma non è selettiva come MA30. Tuttavia, è complementare: quando P1 e P2 non entrano (falsi breakout di MA3/MA7), P3 può cogliere il movimento successivo.

---

### 10.4 Pattern 4: MA30 SELL → MA121 cross (P4)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA30 (30 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 2.64 |
| Trade totali | 245 |
| Win Rate | 43.3% |
| PnL medio | +633.3pt |
| Tenuta media | 41 giorni |

**Entry**: prezzo D1 chiude sotto MA30 (crossover bearish). Richiede un mese di debolezza.

**Exit**: prezzo D1 chiude sopra MA121 (crossover bullish).

**Caratteristica**: **Sharpe più alto del gruppo SELL** (2.64) e PnL medio più alto (+633pt). MA30 è abbastanza lenta da filtrare il rumore ma abbastanza reattiva da non perdere l'inizio del trend. 245 trade in 17 anni (~14/anno) — selettivo ma profittevole.

**Perché ha Sharpe più alto di P1/P2**: MA30 dà meno falsi segnali di MA3/MA7. I trend devono essere abbastanza forti da rompere MA30, e una volta che lo fanno, tendono a persistere fino a MA121.

---

### 10.5 Pattern 5: MA365 SELL → MA7 cross (P5)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA365 (365 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA7 (7 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 3.35 |
| Trade totali | 60 |
| Win Rate | 45.0% |
| PnL medio | +241.6pt |
| Tenuta media | 5 giorni |

**Entry**: prezzo D1 chiude sotto MA365 (crossover bearish annuale). Segnale molto raro (60 in 17 anni, ~3.5/anno). Indica l'inizio di un bear market strutturale.

**Exit**: prezzo D1 chiude sopra MA7 (crossover bullish settimanale). Esce rapidamente al primo rimbalzo.

**Particolarità**: questo pattern INVERTE la logica degli altri — entry su MA lunga (365), exit su MA corta (7). È un pattern da "bear market rally": vende quando inizia il downtrend annuale e compra al primo rimbalzo settimanale. Trade brevi (5 giorni).

**Sharpe 3.35**: è lo Sharpe più alto di tutti i pattern Analisi 2. Ma con soli 60 trade, la significatività statistica è limitata.

**Perché l'inversione entry/exit?**: in un downtrend annuale, i rimbalzi su MA7 sono frequenti ma brevi. Uscire rapidamente permette di catturare la discesa principale senza farsi prendere nei rimbalzi.

---

### 10.6 Pattern 6: MA121 BUY → MA182 cross (P6)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA121 (121 periodi) |
| Direzione | BUY (1) |
| Linea uscita | MA182 (182 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 2.20 |
| Trade totali | 118 |
| Win Rate | 39.8% |
| PnL medio | +393.6pt |
| Tenuta media | 39 giorni |

**Entry**: prezzo D1 chiude SOPRA MA121 (crossover bullish semestrale). Segnale rialzista.

**Exit**: prezzo D1 chiude SOTTO MA182 (crossover bearish di ~9 mesi).

**Primo pattern BUY del gruppo**. I pattern BUY sono meno profittevoli dei SELL in questo dataset (EURUSD in trend ribassista secolare). Tuttavia, P6 ha Sharpe 2.20 e PnL medio +394pt — rispettabile. 118 trade in 17 anni (~7/anno).

**Perché exit su MA182 e non MA121?**: entry su MA121 e exit su MA182 danno spazio al trend. Se l'exit fosse su MA121, il segnale sarebbe "entra quando MA121 fa bullish cross, esci quando fa bearish cross" — troppo stretto. MA182 dà più respiro.

---

### 10.7 Pattern 7: MA365 BUY → MA182 cross (P7)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA365 (365 periodi) |
| Direzione | BUY (1) |
| Linea uscita | MA182 (182 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 1.51 |
| Trade totali | 55 |
| Win Rate | 41.8% |
| PnL medio | +286.9pt |
| Tenuta media | 47 giorni |

**Entry**: prezzo D1 chiude sopra MA365 (crossover bullish annuale). Segnale rialzista raro (55 in 17 anni).

**Exit**: prezzo D1 chiude sotto MA182 (crossover bearish). Exita prima che MA365 venga persa.

**Caratteristica**: entry rarissima (~3/anno), trade lunghi (47 giorni). Sharpe 1.51 accettabile. Compra all'inizio di un bull market annuale, vende quando il trend di 9 mesi gira.

---

### 10.8 Pattern 8: MA365 BUY → MA121 cross (P8)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA365 (365 periodi) |
| Direzione | BUY (1) |
| Linea uscita | MA121 (121 periodi) |
| SL | 0 (nessuno) |
| TP | 0 (nessuno) |
| Sharpe storico | 1.08 |
| Trade totali | 56 |
| Win Rate | 50.0% |
| PnL medio | +188.7pt |
| Tenuta media | 47 giorni |

**Entry**: prezzo D1 chiude sopra MA365 (crossover bullish annuale). Stessa entry di P7.

**Exit**: prezzo D1 chiude sotto MA121 (crossover bearish semestrale).

**Differenza da P7**: exit su MA121 (più veloce) invece di MA182. Chiude prima. Sharpe inferiore (1.08 vs 1.51) ma Win Rate più alto (50% vs 42%). Trade più brevi. P8 è il più debole del gruppo BUY ma ha comunque Sharpe positivo.

---

### 10.9 Pattern 9: MA30 BUY → SL=MA365 TP=150pt (P9)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA30 (30 periodi) |
| Direzione | BUY (1) |
| SL linea | MA365 (365 periodi) |
| TP | 150 punti (15 pip) |
| Sharpe storico | 8.77 |
| Trade totali | 111 |
| Win Rate | 93.7% |
| PnL medio | +98.9pt |
| Tenuta media | 1.7 giorni |

**Entry**: prezzo D1 chiude SOPRA MA30 (crossover bullish). Segnale rialzista mensile.

**Hard SL**: piazzato al valore di MA365 al momento dell'entry. Valido SOLO se MA365 < entry (SL sotto per BUY). Se MA365 > entry, il trade viene saltato con log: `Pattern 9 SKIPPED: SL line MA365 non piazzabile (lato sbagliato o lettura fallita)`.

**Dynamic SL**: a ogni chiusura D1, se il prezzo chiude SOTTO MA365 (crossover bearish), la posizione viene chiusa.

**TP**: 150pt (15 pip). Se il prezzo sale di 150 punti dall'entry, la posizione viene chiusa a profitto.

**Lot sizing**: il lotto è calcolato sulla distanza `entry - MA365`. Più MA365 è vicino, più il lotto è grande. La protezione `InpMinSLDistPts` (default 50pt) impedisce l'apertura con distanze troppo piccole.

**Esempio storico concreto** (dal debug):
```
Entry: 2010.01.04 MA7 BUY @ 1.44111
SL: MA365 = 1.39455 (465pt sotto)
TP: 150pt
→ TP colpito il 2010.01.05 a 1.43624 (high del giorno 1.44830 > 1.44111+0.00150=1.44261)
PnL = 150 - 15(spread) = +135pt
Trade durato: 1 giorno
```

**Perché Sharpe 8.77?**: Win Rate 93.7% combinato con PnL medio +98.9pt. Solo il ~6% dei trade colpisce SL. Questo accade perché MA365 è tipicamente molto lontana dal prezzo in un trend rialzista, quindi il TP 150pt viene colpito quasi sempre prima.

**Rischio**: quando MA365 viene colpita, la perdita è enorme (tutto il `riskDist`). Il Win Rate del 93.7% compensa, ma un periodo di forte volatilità con stop consecutivi può essere devastante.

---

### 10.10 Pattern 10: MA7 SELL → SL=MA365 TP=150pt (P10)

| Proprietà | Valore |
|-----------|--------|
| Linea entrata | MA7 (7 periodi) |
| Direzione | SELL (2) |
| SL linea | MA365 (365 periodi) |
| TP | 150 punti (15 pip) |
| Sharpe storico | 2.98 |
| Trade totali | 291 |
| Win Rate | 93.5% |
| PnL medio | +69.5pt |
| Tenuta media | 2.4 giorni |

**Entry**: prezzo D1 chiude SOTTO MA7 (crossover bearish). Segnale ribassista settimanale.

**Hard SL**: piazzato al valore di MA365 all'entry. Valido SOLO se MA365 > entry (SL sopra per SELL). Se MA365 < entry, trade saltato.

**Dynamic SL**: a ogni chiusura D1, se il prezzo chiude SOPRA MA365 (crossover bullish), la posizione viene chiusa.

**TP**: 150pt (15 pip). Se il prezzo scende di 150 punti dall'entry, chiusura a profitto.

**Differenza da P9**: mirror speculare in direzione SELL con entry su MA7 invece di MA30. Più trade (291 vs 111), Sharpe inferiore (2.98 vs 8.77). MA7 è più reattiva di MA30, quindi genera più segnali ma di qualità leggermente inferiore.

---

## 11. Risk Management

### 11.1 Parametri Configurabili

| Input MQL5 | Default | Range | Descrizione |
|-----------|---------|-------|-------------|
| `InpRiskPct` | 1.0 | 0.1–10.0 | Percentuale di equity rischiata per trade |
| `InpLotFixed` | 0.0 | 0.0–100.0 | Lotto fisso (0 = usa rischio %) |
| `InpMaxLot` | 0.0 | 0.0–100.0 | Lotto massimo assoluto (0 = usa limite broker) |
| `InpMaxSpread` | 50 | 0–500 | Spread massimo in punti per aprire (0 = disabilita) |
| `InpMinSLDistPts` | 50 | 10–1000 | Distanza minima SL in punti (protezione lotti enormi) |
| `InpMaxPos` | 20 | 0–100 | Max posizioni totali (0 = illimitato) |
| `InpMaxPerPattern` | 1 | 0–10 | Max posizioni per pattern (0 = illimitato) |

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
   → Stop-loss inviato al broker all'apertura
   → Protegge da gap intraday e disconnessioni
   → Attivo solo per pattern con slLine > 0

2. Dynamic SL cross check
   → Verificato a ogni chiusura D1
   → Chiude se la SL line fa crossover avverso
   → Attivo per tutti i pattern con slLine > 0

3. Exit cross check
   → Verificato a ogni chiusura D1
   → Chiude se la exit line fa crossover avverso
   → Attivo per tutti i pattern con exit > 0
```

---

## 12. Guida all'Uso

### 12.1 Installazione

1. Copiare `EA/EA_Pattern.mq5` in `MetaTrader 5/MQL5/Experts/` (oppure il file direttamente dalla root `EA_Pattern.mq5`)
2. Copiare `Indicatori/PaPP_Median.ex5` in `MetaTrader 5/MQL5/Indicators/`
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

I dati sono stati divisi in:
- **Training set**: 70% (2994 barre, 2009.12.31 → ~2016)
- **Test set**: 30% (1284 barre, ~2016 → 2026.06.19)

I pattern sono stati selezionati sul training e validati sul test.

### 13.2 Risultati Top 20 Pattern Training → Test

```
Pattern                                                     Train_Sh  Test_Sh  Train_N  Test_N  Train_Win  Test_Win
MA7 BUY | TP SL=MA14 TP=20                                    99*     −2.20     114      170    100.0%     58.8%
MA7 BUY | TP SL=MA14 TP=30                                    99*     −2.03     114      170    100.0%     58.8%
MA7 BUY | TP SL=MA365 TP=20                                   99*     10.57     174      170    100.0%     97.1%
MA7 BUY | TP SL=MA365 TP=30                                   99*     10.60     174      170    100.0%     97.1%
MA7 BUY | TP SL=MA365 TP=60                                   99*     10.71     172      170    100.0%     97.1%
MA7 BUY | TP SL=MA365 TP=150                                  99*     10.86     165      170    100.0%     95.3%
MA3 BUY | TP SL=MA14 TP=20                                    99*      6.53     233      319    100.0%     78.4%
```

*Sharpe 99.0 = artefatto std=0

**Pattern con SL=MA365** mantengono Sharpe altissimo anche in test (10.57–10.86). Questo conferma che MA365 come SL è robusto.

**Pattern con SL=MA14** crollano in test (Sharpe negativo). Segno che TP=20 su SL=MA14 è un artefatto statistico.

### 13.3 Validazione dei Pattern Selezionati per l'EA

I pattern Analisi 2 (P1–P8) non sono nella top 20 perché la validazione test set dello script testa solo pattern Analisi 3 (SL+TP). La robustezza di P1–P8 è stata verificata manualmente confrontando le performance su periodi diversi.

---

## 14. Limitazioni e Rischi Noti

### 14.1 Dipendenza dall'Indicatore PaPP_Median.ex5

L'EA dipende dall'indicatore personalizzato per tutti i valori delle 8 linee. Se l'indicatore:
- Non è presente in `MQL5/Indicators/` → INIT_FAILED
- Ha un bug nei buffer oltre l'indice 1 → crossover errati
- Non calcola correttamente su D1 → fallback chart TF con possibili discrepanze

**Il fix del dead-code branch in PaPP_Median.OnCalculate() è ancora aperto.**

### 14.2 Discrepanza D1 — Doppio Percorso di Lettura

`ReadBufD1()` ha due percorsi:
1. Handle D1 diretto (preferito)
2. Fallback sul chart TF

Se il percorso 1 fallisce `(g_indD1 == INVALID_HANDLE)`, il fallback legge dal chart TF corrente, che può dare valori diversi dal D1 reale. Su timeframe brevi (M15, M30), MA365 calcolata sui prezzi M15 è molto diversa da MA365 calcolata sui prezzi D1.

Il log avvisa se il handle D1 fallisce:
```
WARNING: g_indD1 fallito - usero' solo chart fallback
```

**Soluzione**: se vedi questo warning, attacca l'EA su un chart D1 (non M15/H1). Il fallback sarà esatto.

### 14.3 Gap Intraday (P1–P8)

Gli 8 pattern senza hard SL (P1–P8) NON hanno protezione broker-side contro gap intraday. La posizione rimane aperta fino al controllo D1 successivo. Su strumenti volatili o in eventi macro (NFP, BCE, SNB), un gap può causare perdite significative.

**Solo P9–P10 hanno hard SL** (al valore della SL line al momento entry).

### 14.4 Accoppiamento tra Pattern

I pattern 1–4 (SELL su MA3/7/14/30 → MA121) possono entrare simultaneamente su segnali ravvicinati. Con `InpMaxPerPattern = 1`, ogni pattern apre 1 posizione, ma `InpMaxPos = 20` permette fino a 20 posizioni totali. In teoria, 4 posizioni SELL correlate possono essere aperte contemporaneamente, amplificando il rischio direzionale.

### 14.5 Overfitting e Cambio di Regime

I pattern sono stati selezionati su 17 anni di dati EURUSD (2009–2026). L'EURUSD ha avuto un trend ribassista dominante in questo periodo (da 1.60 a 1.04). Se il mercato cambia regime (es. EURUSD torna in un trend rialzista pluriennale), i pattern SELL potrebbero degradare significativamente.

**Mitigazione**: la diversificazione BUY/SELL (P6–P8 BUY + P1–P5 SELL + P9 BUY + P10 SELL) bilancia parzialmente la direzionalità.

### 14.6 Spread Reali vs Assunti

L'analisi usa spread 15pt (1.5 pip) su EURUSD D1. Spread reali su D1 sono tipicamente 10–20pt, ma possono salire a 50–100pt in momenti di illiquidità. L'EA controlla `InpMaxSpread` (default 50pt) all'apertura, ma spread intermedi (20–50pt) erodono il profitto atteso.

**Impatto**: i pattern con PnL medio basso (es. P8: +188pt) soffrono di più di spread alti (erodono 10–20% del profitto). I pattern con PnL medio alto (P4: +633pt) risentono meno.

### 14.7 Rischio P9/P10: Perdite Concentrate

P9 e P10 hanno Win Rate >93% ma perdite grandi quando lo SL viene colpito. In uno scenario di forte trend avverso (es. 3–4 stop consecutivi su P9 in un mercato che scende), la perdita cumulativa può essere significativa.

**Esempio**: 100 trade P9: ~93 vincenti (+99pt medi) e ~7 perdenti (−465pt medi).
PnL netto stimato = 93 × 99 − 7 × 465 = 9.207 − 3.255 = +5.952pt.

Profittevole nel lungo termine, ma la distribuzione non è uniforme — le perdite tendono a concentrarsi in periodi di alta volatilità.

---

## Appendice A: Glossario

| Termine | Definizione |
|---------|-------------|
| **Punto (pt)** | 0.00001 per EURUSD a 5 decimali. 10pt = 1 pip |
| **Pip** | 0.0001 per EURUSD. 1 pip = 10pt |
| **Tick** | Movimento minimo del prezzo. Su EURUSD = 0.00001 = 1pt |
| **Tick Value** | Valore monetario di un tick. Per 1 lotto standard EURUSD ≈ $10 |
| **Crossover** | Quando il prezzo CHIUDE oltre una MA dopo aver chiuso dall'altro lato il giorno prima |
| **Bullish cross** | D1 close > MA (dopo essere stato ≤ MA) |
| **Bearish cross** | D1 close < MA (dopo essere stato ≥ MA) |
| **Sharpe Ratio** | (Avg PnL) / (Std PnL) × √252. ≥1 = buono, ≥2 = ottimo, ≥3 = eccellente |
| **Profit Factor** | Somma profitti / |Somma perdite|. ≥1.5 = buono |
| **SL dinamico** | SL che segue il valore corrente della linea (es. MA365) |
| **Hard SL** | Stop-loss broker-side inviato all'apertura |
| **Floating SL** | SL che non è un ordine fermo ma viene controllato a ogni barra |
| **Risk-% sizing** | Calcolo lotto: `(equity × Risk%) / (riskDist × tickValue / tickSize)` |
| **Walk-forward** | Training su 70% dati, validation su 30% non visti dal training |

## Appendice B: Codice Colore nel Log

| Messaggio | Significato |
|-----------|-------------|
| `=== SEGNALE ===` | Inizio elaborazione giornaliera |
| `>>> APERTURA [N]` | Nuova posizione aperta per pattern N |
| `>>> CHIUSO [N]` | Posizione chiusa per pattern N |
| `SKIPPED: SL line` | Trade saltato (SL non piazzabile) |
| `SKIPPED: riskDist` | Trade saltato (distanza minima) |
| `ha gia' N posizioni` | Limite per-pattern raggiunto |
| `WARNING:` | Non bloccante (es. linea invalida) |
| `FATAL:` | Bloccante (es. indicatore non trovato) |
| `ERR entrata` | Errore broker all'apertura (retcode) |

## Appendice C: Lista Completa dei File

| File | Path | Descrizione |
|------|------|-------------|
| `EA/EA_Pattern.mq5` | `/MQL5/Experts/` | EA multi-pattern v2.02 |
| `Analisi/Export_PAPP.mq5` | `/MQL5/Scripts/` | Script esportazione CSV (legacy) |
| `Indicatori/PaPP_Median.ex5` | `/MQL5/Indicators/` | Indicatore personalizzato (compilato) |
| `Analisi/pattern_mining.py` | — | Script Python analisi pattern v3 |
| `Analisi/PAPP_Export.csv` | — | Dataset D1 EURUSD 4278 barre |
| `DOCUMENTAZIONE.md` | — | Questo documento |

## Appendice D: Sequenza Completa dei Comandi

```bash
# 1. Esportare i dati (da MetaTrader 5)
# Eseguire Export_PAPP.mq5 su EURUSD D1
# Output: <CARTELLA_DATI>\MQL5\Files\PAPP_Export.csv

# 2. Copiare il CSV nella directory del progetto
cp "/percorso/MT5/Files/PAPP_Export.csv" /home/pietro_giacobazzi/Desktop/PAPP_EA/Analisi/

# 3. Eseguire l'analisi completa
cd Analisi && python3 pattern_mining.py PAPP_Export.csv --spread=15

# 4. Con walk-forward validation
python3 pattern_mining.py PAPP_Export.csv --spread=15 --train-pct=0.7

# 5. Con split su data specifica
python3 pattern_mining.py PAPP_Export.csv --spread=15 --split-date=2020.01.01

# 6. Copiare EA su MT5
cp EA/EA_Pattern.mq5 "/percorso/MT5/MQL5/Experts/EA_Pattern.mq5"

# 7. Copiare indicatore su MT5
cp Indicatori/PaPP_Median.ex5 "/percorso/MT5/MQL5/Indicators/PaPP_Median.ex5"

# 8. Compilare in MetaEditor (F7)
# 9. Attaccare su chart EURUSD
```
