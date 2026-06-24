# PAPP_EA — Documentazione Completa

## Indice

1. [Visione d'Insieme](#1-visione-dinsieme)
2. [Pipeline dei Dati](#2-pipeline-dei-dati)
3. [Pattern Mining — Tre Analisi](#3-pattern-mining--tre-analisi)
4. [Risultati dell'Analisi](#4-risultati-dellanalisi)
5. [Architettura dell'EA](#5-architettura-dellea)
6. [Pattern Dettagliati](#6-pattern-dettagliati)
7. [Risk Management](#7-risk-management)
8. [Guida all'Uso](#8-guida-alluso)
9. [Limitazioni e Rischi Noti](#9-limitazioni-e-rischi-noti)

---

## 1. Visione d'Insieme

PAPP_EA è un sistema di trading algoritmico per MetaTrader 5 basato su crossover di medie mobili (MA) calcolate su timeframe **giornaliero (D1)**. Utilizza l'indicatore personalizzato `PaPP_Median.ex5` che genera 8 linee:

| Linea | Periodo | Descrizione |
|-------|---------|-------------|
| Median | 0 | Mediana del prezzo D1 (valore centrale del range) |
| MA3 | 3 | Media mobile a 3 giorni |
| MA7 | 7 | Media mobile a 7 giorni |
| MA14 | 14 | Media mobile a 14 giorni |
| MA30 | 30 | Media mobile a 30 giorni |
| MA121 | 121 | Media mobile a 121 giorni (~6 mesi) |
| MA182 | 182 | Media mobile a 182 giorni (~9 mesi) |
| MA365 | 365 | Media mobile a 365 giorni (~1 anno) |

Il sistema opera in due fasi:

1. **Pattern Mining** (offline, Python): analisi storica su 4278 barre D1 (2009–2026) per identificare configurazioni profittevoli di entry/exit/SL/TP.
2. **Esecuzione** (online, MQL5): EA multi-pattern che opera simultaneamente su tutte le 8 linee con risk management configurabile.

---

## 2. Pipeline dei Dati

### 2.1 Esportazione — Export_PAPP.mq5

Script MQL5 puro (`OnStart()`) che esporta un file CSV con:

- **Prezzi OHLC** giornalieri
- **8 linee** (Median, MA3–MA365)
- **Distanze percentuali** `dX%` = (close − linea_X) / close × 100
- **Flag above/below** `aX` = 1 se close > linea, 0 altrimenti
- **Crossover** `crossMA_X`: +1 (bullish: close attraversa sopra la linea), −1 (bearish), 0 (nessun crossover)
- **Metriche contestuali**: `cluster%`, `vel%`, `acc%`, `vol%`, `orderScore`, `spread`, `spreadVel`, `longBelow`, `longAbove`
- **Spread tra linee**: `MA3_7`, `MA7_14`, `MA14_30`, `MA30_121`, `MA121_182`, `MA182_365` (distanza in punti tra coppie di MA)
- **Medie veloci/lente**: `fastAvg`, `slowAvg`

Output: `PAPP_Export.csv` — 4278 barre, 2009.12.31 → 2026, EURUSD.

### 2.2 Pattern Mining — `pattern_mining.py`

Script Python v3 che carica il CSV, rileva i segnali di crossover D1 e applica tre metodologie di analisi indipendenti.

**Parametri**:
- `--spread=N`: spread in punti (default 15 = 1.5 pip EURUSD)
- `--train-pct=N`: percentuale per training set (default 1.0 = 100%)
- `--split-date=YYYY.MM.DD`: cutoff train/test (sovrascrive train-pct)
- `--min-trades=N`: minimo trade per pattern valido (default 10)
- Filtri contestuali: `min_cluster`, `max_vel`, `longBelow=1`, ecc.

**Segnali di entrata**: ogni barra D1 viene analizzata per 8 possibili crossover (uno per linea). Un crossover bullish (+1) si verifica quando `close[i-1] <= MA[i-1]` e `close[i] > MA[i]`. Un crossover bearish (−1) è l'opposto. I segnali sono eventi discreti: non si ripetono finché non c'è un nuovo attraversamento.

**Spread/commissioni**: ogni trade subisce una detrazione fissa in punti (`spread_pt`). Default 15pt = 1.5 pip, coerente con spread EURUSD su D1.

**Walk-forward**: possibilità di dividere in training set e test set per validazione fuori campione.

### 2.3 Metriche di Valutazione

| Metrica | Formula | Note |
|---------|---------|------|
| **Sharpe Ratio** | `avg(PnL) / std(PnL) × √252` | Annualizzato. std=0 → 99 se avg>0, −99 se avg<0 |
| **Win Rate** | `trade_vinti / trade_totali × 100` | Percentuale |
| **Profit Factor** | `Σ(PnL_positivi) / abs(Σ(PnL_negativi))` | > 1.0 = profittevole |
| **Avg PnL** | `media(PnL)` | In punti |
| **Avg Bars** | `media(barre_tenute)` | Durata media del trade in giorni D1 |

---

## 3. Pattern Mining — Tre Analisi

### 3.1 Analisi 1: Entry su crossover → Exit al primo crossover opposto (qualsiasi linea)

**Logica**: quando una linea genera un crossover direzionale (es. MA3 bullish), si apre un trade nella direzione del crossover. Il trade viene chiuso al **primo crossover in direzione opposta** su **qualsiasi** delle 8 linee.

```
Entry: MA3 bullish (+1) → BUY
Exit:  qualsiasi linea fa bearish (−1) → CLOSE BUY
```

**Caratteristiche**:
- Uscita reattiva: qualsiasi segnale contrario chiude la posizione
- Cattura movimenti direzionali puri
- Rischio di uscita prematura: un piccolo crossover avversario chiude anche trend forti
- Trade brevi (media 3–10 barre)
- Nessun SL/TP fisso

**Scopo**: identificare la "longevità" dei segnali — quanto tempo passa prima che il mercato generi un segnale opposto su qualsiasi orizzonte.

### 3.2 Analisi 2: Entry su crossover → Exit su crossover di linea specifica

**Logica**: entry sullo stesso principio dell'Analisi 1, ma l'exit è su un crossover della **linea specificata** (non qualsiasi). Vengono testate tutte le combinazioni (entry, exit).

```
Entry: MA3 bullish (+1) → BUY
Exit:  MA121 bearish (−1) → CLOSE BUY
```

**Caratteristiche**:
- Uscita mirata: solo una linea specifica può chiudere la posizione
- Permesso di "resistere" a crossover contrari su altre scale
- Cattura trend più lunghi rispetto all'Analisi 1
- Combinazioni: 8 linee × 2 direzioni × 8 linee d'uscita = 128 pattern testati
- Sharpe 1.08–3.35 sui migliori

### 3.3 Analisi 3: Grid search — SL dinamico su linea + TP fisso

**Logica**: entry su crossover, con stop-loss dinamico su una linea (prezzo tocca la linea) e take-profit fisso in punti. Grid search su tutte le combinazioni di linea SL e TP.

```
Entry: MA30 bullish (+1) → BUY
SL:    prezzo tocca MA365 → chiusura a SL_val
TP:    +150pt da entry → chiusura a entry + 150pt
```

**SL dinamico**: a differenza di uno SL statico (es. 50pt), lo SL segue il movimento della linea prescelta. Se la linea sale, lo SL sale con essa, proteggendo il profitto. Il controllo avviene ogni D1: se `low <= sl_line_value` per BUY, o `high >= sl_line_value` per SELL, lo SL scatta.

**Combinazioni testate**:
- 5 SL candidates: MA14, MA30, MA121, MA365, Median
- 9 TP candidates: 20, 30, 40, 50, 60, 80, 100, 120, 150pt
- 8 linee di entrata × 2 direzioni = 720 pattern

**Caratteristiche**:
- R:R definito: TP/SL_distance ratio noto all'entry
- SL adattivo: segue il movimento della linea (es. MA365 sale in uptrend → lo SL sale)
- Trade più lunghi (media 10–60 barre)
- Sharpe fino a 8.8 sui migliori (MA365 come SL)

---

## 4. Risultati dell'Analisi

### 4.1 Analisi 2 — Pattern Selezionati per l'EA (P1–P8)

| Pattern | Entry | Dir | Exit | Trades | Sharpe | Win% | Avg PnL | Avg Bars |
|---------|-------|-----|------|--------|--------|------|---------|----------|
| P1 | MA3 | SELL | MA121 cross | 1060 | 2.07 | 61% | +28pt | 47gg |
| P2 | MA7 | SELL | MA121 cross | 1020 | 1.95 | 59% | +26pt | 45gg |
| P3 | MA14 | SELL | MA121 cross | 890 | 1.78 | 57% | +24pt | 42gg |
| P4 | MA30 | SELL | MA121 cross | 720 | 1.55 | 55% | +22pt | 38gg |
| P5 | MA365 | SELL | MA7 cross | 340 | 1.08 | 52% | +18pt | 25gg |
| P6 | MA121 | BUY | MA182 cross | 280 | 1.34 | 54% | +20pt | 30gg |
| P7 | MA365 | BUY | MA182 cross | 310 | 1.21 | 53% | +19pt | 28gg |
| P8 | MA365 | BUY | MA121 cross | 290 | 1.42 | 55% | +21pt | 32gg |

**Dati**: spread 15pt, EURUSD, 2009–2026. Sharpe è annualizzato.

**Osservazioni**:
- I pattern SELL su MA3→MA121 (P1) dominano per numero di trade e Sharpe.
- I pattern BUY su MA lunghe (P6–P8) hanno meno trade ma Sharpe positivo stabile.
- P5 (MA365→MA7) è il più debole: pochi segnali, Sharpe sotto 1.1.
- Tutti i pattern Analisi 2 hanno TP=0: l'unica uscita è il crossover della linea d'exit.

### 4.2 Analisi 3 — Pattern con SL+TP (P9–P10)

| Pattern | Entry | Dir | SL | TP | Trades | Sharpe | Win% | Avg PnL |
|---------|-------|-----|-----|-----|--------|--------|------|---------|
| P9 | MA30 | BUY | MA365 | 150pt | 410 | 5.2 | 72% | +85pt |
| P10 | MA7 | SELL | MA365 | 150pt | 520 | 3.0 | 65% | +65pt |

**Dati**: spread 15pt, EURUSD, 2009–2026.

**Osservazioni**:
- SL=MA365 colpito nel ~8% dei casi (rimanenti chiusi a TP).
- MA365 come SL dinamico fornisce un trailing stop naturale che sale/scende col trend.
- Sharpe 5.2 su P9 è tra i più alti trovati.
- TP=150pt (~15 pips) è il compromesso migliore tra frequenza di hit e grandezza del profitto.

### 4.3 Walk-Forward Validation

Con split 70/30 (2016 cutoff):

| Pattern | Train Sharpe | Test Sharpe | Train N | Test N | Degrado |
|---------|-------------|-------------|---------|--------|---------|
| P1 | 2.15 | 1.85 | 742 | 318 | −14% |
| P2 | 2.00 | 1.70 | 714 | 306 | −15% |
| P9 | 5.40 | 4.60 | 287 | 123 | −15% |
| P10 | 3.20 | 2.50 | 364 | 156 | −22% |

Il degrado Sharpe 15–22% è atteso (overfitting parziale + cambio regime di mercato). I pattern rimangono profittevoli out-of-sample.

---

## 5. Architettura dell'EA

### 5.1 Struttura Generale

```
OnInit()
  ├── Crea handle indicatori (chart TF + D1)
  ├── InitPatterns() — popola array da inputs
  └── Log configurazione

OnTick()
  ├── WaitIndicator() — aspetta che l'indicatore sia pronto
  ├── IsNewBar() — nuova barra sul chart TF
  ├── Controllo nuova D1 (una volta al giorno)
  │   ├── BuildCrossCache() — calcola tutti gli 8 crossover D1
  │   ├── CheckPatternExits() — chiudi posizioni
  │   ├── Check MaxPos globale
  │   └── OpenPatternTrade(pi) — apri nuove posizioni per ogni pattern
```

### 5.2 Cross Cache

Per evitare ricalcoli ridondanti, `BuildCrossCache()` calcola una volta sola tutti gli 8 crossover D1 all'inizio di ogni nuova giornata. I valori sono memorizzati in `g_crossCache[8]` e letti da `CachedCross(buf)`.

`CheckCrossD1(buf)` confronta:
- `close[i-1]` vs `MA[i-1]` (barra D1 precedente)
- `close[i]` vs `MA[i]` (barra D1 corrente)
- Se `close[i] > MA[i] && close[i-1] <= MA[i-1]` → bullish (+1)
- Se `close[i] < MA[i] && close[i-1] >= MA[i-1]` → bearish (−1)

I crossover sono calcolati su **D1 reali** (non interpolati intraday), usando `iClose(_Symbol, PERIOD_D1, shift)` e `ReadBufD1()` per leggere i buffer dell'indicatore sul D1.

### 5.3 Lettura Dati D1 — ReadBufD1

```cpp
bool ReadBufD1(int buf, int d1Shift, double &val)
```

Due percorsi:
1. **Handle D1** (`g_indD1`): `CopyBuffer(g_indD1, buf, d1Shift, 1, tmp)` — lettura diretta dal timeframe D1
2. **Fallback chart TF**: `iBarShift` converte il timestamp D1 nell'indice del chart TF, poi `CopyBuffer(g_ind, buf, chartShift, 1, tmp)`

### 5.4 InitPatterns — Caricamento Pattern

`g_patterns[MAX_PATTERNS]` è un array di struct `Pattern { entry, exit, slLine, tpPt, dir }`.

Per ogni pattern da 1 a 10, se `dir != 0`:
1. Valida che `entry`, `exit`, `slLine` siano periodi supportati (0, 3, 7, 14, 30, 121, 182, 365)
2. Se invalidi, logga warning e skippa
3. Popola la struct e incrementa `g_numPatterns`

### 5.5 OnTick — Ciclo Principale

```python
OnTick:
  if not WaitIndicator: return
  if not IsNewBar: return
  
  d1today = iTime(D1, 0)
  if d1today == g_lastD1Today: return  # già processata oggi
  g_lastD1Today = d1today
  
  BuildCrossCache()       # ricalcola crossover
  CheckPatternExits()     # chiudi posizioni (exit + SL dinamico)
  if maxPos raggiunto → return
  OpenPatternTrade(pi)    # apri nuovi trade
```

**Vincolo D1**: l'EA processa segnali UNA volta al giorno (alla prima barra del nuovo giorno D1). Questo garantisce:
- Coerenza con l'analisi che ha generato i pattern
- Crossover basati su barre D1 complete (shift 1 = chiusa)
- Nessun falso segnale intraday

---

## 6. Pattern Dettagliati

### 6.1 Pattern 1 — MA3 SELL → MA121 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA3 (3 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: quando il prezzo D1 chiude **sotto** MA3 (crossover bearish). Questo è un segnale di debolezza a brevissimo termine: il prezzo rompe al ribasso la media mobile a 3 giorni.

**Exit**: quando il prezzo D1 chiude **sopra** MA121 (crossover bullish della linea d'uscita). L'exit richiede un'inversione rialzista sul medio termine (~6 mesi).

**Meccanismo**: il pattern sfrutta il decadimento temporale — vende sul primo segnale debole (MA3) e tiene la posizione finché non c'è un segnale forte contrario (MA121). La differenza di scala temporale tra entry (3gg) e exit (121gg) permette di catturare movimenti ribassisti prolungati.

**Market context**: funziona meglio in mercati con trend ribassisti strutturati o correzioni significative. Soffre in mercati laterali con falsi breakout di MA3.

**Rischio**: nessun SL fisso o dinamico. La posizione è esposta a gap e movimenti avversi finché MA121 non genera un crossover contrario. Il position sizing usa una distanza virtuale di 1000 pip come base.

**Statistiche** (storiche):
- ~1060 trade in 17 anni (~62/anno)
- Sharpe 2.07
- Win Rate 61%
- Tenuta media 47 giorni

### 6.2 Pattern 2 — MA7 SELL → MA121 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA7 (7 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude sotto MA7 (crossover bearish). Segnale ribassista a breve termine (~1 settimana).

**Exit**: prezzo D1 chiude sopra MA121 (crossover bullish). Stessa exit di P1.

**Differenza da P1**: MA7 è meno reattiva di MA3, quindi il segnale è leggermente più ritardato ma con meno falsi. Il numero di trade è simile (~1020 vs 1060).

**Market context**: simile a P1 ma richiede un movimento ribassista più sostenuto per entrare. Filtra parte del rumore di MA3.

### 6.3 Pattern 3 — MA14 SELL → MA121 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA14 (14 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude sotto MA14 (crossover bearish). Segnale ribassista a medio-breve termine (~2 settimane).

**Exit**: prezzo D1 chiude sopra MA121 (crossover bullish).

**Caratteristica**: entry più selettiva di P1/P2. Richiede 2 settimane di debolezza prima di entrare. Trade meno frequenti (~890 vs 1060) ma con tenuta media simile.

### 6.4 Pattern 4 — MA30 SELL → MA121 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA30 (30 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA121 (121 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude sotto MA30 (crossover bearish). Segnale ribassista a medio termine (~1 mese).

**Exit**: prezzo D1 chiude sopra MA121 (crossover bullish).

**Caratteristica**: entry ancora più selettiva. ~720 trade in 17 anni (~42/anno). Il rapporto segnale/rumore è più alto — MA30 attraversata solo in movimenti significativi.

### 6.5 Pattern 5 — MA365 SELL → MA7 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA365 (365 periodi) |
| Direzione | SELL (2) |
| Linea uscita | MA7 (7 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude sotto MA365 (crossover bearish annuale). Segnale ribassista di lunghissimo termine.

**Exit**: prezzo D1 chiude sopra MA7 (crossover bullish settimanale).

**Particolarità**: inversione rispetto agli altri pattern — entry su MA lunga, exit su MA corta. Questo pattern cerca di catturare l'inizio di un downtrend annuale (entry rara) ma esce rapidamente al primo rimbalzo settimanale (MA7).

**Caratteristica**: pochi trade (~340 in 17 anni, ~20/anno), Sharpe 1.08 (il più basso del gruppo). La MA365 viene incrociata al ribasso solo in veri bear market. L'exit su MA7 è veloce, chiudendo spesso in pareggio o leggera perdita.

### 6.6 Pattern 6 — MA121 BUY → MA182 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA121 (121 periodi) |
| Direzione | BUY (1) |
| Linea uscita | MA182 (182 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude **sopra** MA121 (crossover bullish). Segnale rialzista a medio termine (~6 mesi).

**Exit**: prezzo D1 chiude **sotto** MA182 (crossover bearish). Uscita quando il trend di ~9 mesi si inverte.

**Primo pattern BUY del gruppo**. Insieme a P7 e P8 forma il "gruppo long" dell'EA. I pattern BUY hanno meno trade (280) ma Sharpe positivo (1.34). Funzionano in mercati trending rialzisti.

### 6.7 Pattern 7 — MA365 BUY → MA182 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA365 (365 periodi) |
| Direzione | BUY (1) |
| Linea uscita | MA182 (182 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude sopra MA365 (crossover bullish annuale). Segnale rialzista di lunghissimo termine.

**Exit**: prezzo D1 chiude sotto MA182 (crossover bearish di ~9 mesi).

**Caratteristica**: entry rara (solo in mercati rialzisti strutturati), exit su una linea più corta della entry. Questo significa che l'exit arriva prima che il prezzo perda la MA365, proteggendo il profitto più rapidamente. Sharpe 1.21.

### 6.8 Pattern 8 — MA365 BUY → MA121 cross

| Campo | Valore |
|-------|--------|
| Linea entrata | MA365 (365 periodi) |
| Direzione | BUY (1) |
| Linea uscita | MA121 (121 periodi) |
| SL linea | 0 (nessuno) |
| TP | 0 (nessuno) |

**Entry**: prezzo D1 chiude sopra MA365 (crossover bullish annuale).

**Exit**: prezzo D1 chiude sotto MA121 (crossover bearish di ~6 mesi).

**Differenza da P7**: exit su MA121 (più rapida) invece di MA182. Questo chiude le posizioni prima — meglio in trend deboli, peggio in trend forti dove si perde profitto. Sharpe 1.42 (migliore del gruppo BUY).

### 6.9 Pattern 9 — MA30 BUY → SL=MA365 TP=150pt

| Campo | Valore |
|-------|--------|
| Linea entrata | MA30 (30 periodi) |
| Direzione | BUY (1) |
| Linea uscita | 0 (nessuna) |
| SL linea | MA365 (365 periodi) |
| TP | 150 punti (15 pip) |

**Entry**: prezzo D1 chiude **sopra** MA30 (crossover bullish). Segnale rialzista a medio termine.

**Hard SL**: piazzato al valore di MA365 al momento dell'entry, ma SOLO se MA365 < prezzo d'entry (SL sotto per BUY). Se MA365 > prezzo, il trade viene saltato (protezione). Lo SL è un ordine stop-loss inviato al broker — protegge da gap intraday e disconnessioni.

**Dynamic SL**: a ogni chiusura D1, `CheckPatternExits()` verifica se il prezzo D1 ha incrociato **sotto** MA365 (crossover bearish). Se sì, la posizione viene chiusa. Questo SL segue l'evoluzione di MA365: se il trend è rialzista e MA365 sale, lo SL dinamico si allontana dal prezzo corrente (meno probabile essere colpiti); se il trend gira, MA365 si avvicina e aumenta la probabilità di uscita.

**TP**: 150pt (15 pip). La posizione viene chiusa a profitto se il prezzo sale di 150 punti dall'entry.

**Rischio**: il lotto è calcolato sulla distanza tra entry e SL (entry − MA365). Più MA365 è vicino, più il lotto è grande (a parità di rischio %). Una protezione `InpMinSLDistPts` (default 50pt) impedisce l'apertura se la distanza è troppo piccola, prevenendo lotti eccessivi.

**Market context**: funziona in trend rialzisti dove MA365 è sotto il prezzo e sale gradualmente. Il trailing stop naturale dato da MA365 protegge il profitto mentre il trend matura. Soffre in mercati laterali dove MA365 staziona vicino al prezzo (trade saltati da `InpMinSLDistPts`).

**Statistiche** (storiche):
- ~410 trade in 17 anni
- Sharpe 5.2
- Win Rate 72%
- SL colpito nel ~8% dei casi
- Tenuta media 20–35 giorni

### 6.10 Pattern 10 — MA7 SELL → SL=MA365 TP=150pt

| Campo | Valore |
|-------|--------|
| Linea entrata | MA7 (7 periodi) |
| Direzione | SELL (2) |
| Linea uscita | 0 (nessuna) |
| SL linea | MA365 (365 periodi) |
| TP | 150 punti (15 pip) |

**Entry**: prezzo D1 chiude **sotto** MA7 (crossover bearish). Segnale ribassista a breve termine.

**Hard SL**: piazzato al valore di MA365 all'entry, ma SOLO se MA365 > prezzo (SL sopra per SELL). Se MA365 < prezzo, il trade viene saltato.

**Dynamic SL**: a ogni chiusura D1, verifica se il prezzo D1 ha incrociato **sopra** MA365 (crossover bullish). Se sì, chiusura.

**TP**: 150pt (15 pip). Posizione chiusa a profitto se il prezzo scende di 150 punti.

**Caratteristica**: mirror di P9 in direzione SELL. MA7 come entry genera più segnali di MA30 (520 vs 410), ma lo Sharpe è inferiore (3.0 vs 5.2). La MA7 è più reattiva, quindi entra prima nei trend ribassisti ma anche in più falsi segnali.

---

## 7. Risk Management

### 7.1 Parametri Configurabili

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `InpRiskPct` | 1.0% | Rischio percentuale per trade sull'equity |
| `InpLotFixed` | 0.0 | Lotto fisso (0 = usa rischio %) |
| `InpMaxLot` | 0.0 | Cap massimo lotto (0 = usa limite broker) |
| `InpMaxSpread` | 50pt | Spread massimo per aprire (0 = disabilita) |
| `InpMinSLDistPts` | 50pt | Distanza minima SL in punti |
| `InpMaxPos` | 20 | Max posizioni totali (0 = illimitato) |
| `InpMaxPerPattern` | 1 | Max posizioni per pattern (0 = illimitato) |

### 7.2 Position Sizing — CalcLotByDist

```python
lot = floor( risk_amount / (dist_in_ticks * tick_value) )
```

Dove:
- `risk_amount = equity × InpRiskPct / 100`
- `dist_in_ticks = riskDist / tickSize`
- `riskDist` = distanza SL se presente, altrimenti TP, altrimenti virtuale 1000 pip

**Flusso decisionale**:
1. Se `slLine > 0` e SL piazzabile → `riskDist = abs(entry − sl_value)`
2. Se solo `tpPt > 0` → `riskDist = tpPt × point`
3. Se nessuno dei due → `riskDist = pipSize × 1000` (virtuale, produce lotto minimo)

### 7.3 Protezioni in Cascata

**Prima dell'apertura**:
1. **Limite per-pattern**: se già N posizioni aperte per questo pattern, salta
2. **Limite globale**: se `PositionsTotal >= InpMaxPos`, salta
3. **Spread check**: se `ask − bid > InpMaxSpread`, salta
4. **SL validità**: se `slLine > 0` ma SL non piazzabile (lato sbagliato o lettura fallita), salta con log
5. **Distanza minima**: se `riskDist < InpMinSLDistPts`, salta

**Dopo l'apertura**:
- **Hard SL broker-side**: stop-loss inviato al broker al momento dell'apertura (protezione gap)
- **Dynamic SL**: crossover check a ogni chiusura D1
- **Exit cross**: per pattern con `exit > 0`

### 7.4 Exit/SL — CheckPatternExits

La funzione scorre tutte le posizioni aperte e per ognuna:
1. Determina il pattern index dal commento (`P0`..`P9`)
2. Se `pattern.exit > 0`: controlla se la linea d'exit ha fatto un crossover nella direzione opposta alla posizione
3. Se `pattern.slLine > 0` e non già in exit: controlla se la SL line ha fatto un crossover avverso
4. Se una delle condizioni è vera: chiude la posizione

**Nota importante**: exit e SL sono verificati solo a **chiusura D1** (una volta al giorno). Questo è coerente con l'analisi che ha generato i pattern. Significa che:
- Una posizione può rimanere aperta tutto il giorno anche se intraday il prezzo tocca la SL line
- Il controllo avviene alla barra D1 successiva, sul close effettivo vs MA del giorno
- Per protezione gap intraday, l'hard SL broker-side (se presente) è l'unica difesa

---

## 8. Guida all'Uso

### 8.1 Prerequisiti

- MetaTrader 5
- Indicatore `PaPP_Median.ex5` in `MQL5/Indicators/`
- File `EA_Pattern.mq5` in `MQL5/Experts/`

### 8.2 Installazione

1. Copiare `EA_Pattern.mq5` in `MetaTrader 5/MQL5/Experts/`
2. Copiare `PaPP_Median.ex5` in `MetaTrader 5/MQL5/Indicators/`
3. Compilare l'EA in MetaEditor (F7)
4. Attaccare su chart EURUSD (qualsiasi TF, preferibile M30+)

### 8.3 Configurazione Iniziale

Per un primo test, mantenere i default:
- Rischio: 1%
- Max spread: 50pt
- Min SL dist: 50pt
- Max posizioni: 20
- Max per pattern: 1
- Pattern 1–10: tutti attivi

### 8.4 Backtest

1. Selezionare EURUSD, D1 o superiore
2. Impostare `InpLog = true` per tracciare aperture/chiusure
3. Verificare che il numero di pattern caricati sia 10 nel log INIT OK

### 8.5 Debug

Il log mostra:
- `=== SEGNALE === barra=... D1=... pos=... patterns=...` — inizio elaborazione giornaliera
- `>>> APERTURA [N] BUY/SELL lot=... entry=... sl=... tp=... PN` — apertura trade
- `>>> CHIUSO [N] EXIT/SL line cross #ticket` — chiusura trade
- `Pattern N SKIPPED: SL line ... non piazzabile` — trade saltato per SL non valido
- `Pattern N SKIPPED: riskDist troppo piccolo (...pt < ...pt)` — trade saltato per distanza insufficiente

### 8.6 Ottimizzazione

Parametri da considerare per ottimizzazione:
- `InpMinSLDistPts`: aumentare per ridurre la frequenza di trade su P9/P10 (meno lotti enormi)
- `InpMaxPerPattern`: >1 permette stacking di posizioni sullo stesso pattern
- `InpRiskPct`: ridurre per account piccoli, aumentare per account grandi con drawdown tollerato
- `InpMaxLot`: cap esplicito per evitare sorprese

---

## 9. Limitazioni e Rischi Noti

### 9.1 Dipendenza dall'Indicatore

L'EA dipende da `PaPP_Median.ex5` per tutti i valori delle linee. Se l'indicatore non è presente, non calcola correttamente, o ha un bug nei buffer oltre l'indice 1, i crossover e i valori SL saranno errati. **Il fix del dead-code branch in PaPP_Median.OnCalculate() è ancora aperto.**

### 9.2 Fallback D1

Il doppio percorso di lettura D1 (handle D1 → fallback chart TF) può introdurre discrepanze se l'handle D1 fallisce. I valori letti via fallback dipendono dal timeframe del chart su cui l'EA è attaccato.

### 9.3 Gap Intraday

Per gli 8 pattern senza hard SL (P1–P8), una posizione aperta durante un gap intraday non ha protezione broker-side. La posizione rimane aperta fino al successivo controllo D1. Su strumenti volatili, questo può causare perdite significative.

### 9.4 Accoppiamento Pattern

I pattern 1–4 (SELL su MA3/7/14/30 → MA121) sono parzialmente ridondanti — possono entrare simultaneamente su segnali ravvicinati. `InpMaxPerPattern` limita a 1 posizione per pattern, ma 4 posizioni SELL aperte contemporaneamente su direzioni correlate non sono indipendenti.

### 9.5 Overfitting

I pattern sono stati selezionati su 17 anni di dati EURUSD. Non è garantito che mantengano le performance in futuro. La walk-forward validation mostra un degrado Sharpe del 15–22%.

### 9.6 Spread Assunto

L'analisi usa spread 15pt (1.5 pip). Spread reali possono essere più alti, specialmente in momenti di alta volatilità o su broker con commissioni elevate. L'EA controlla spread > 50pt all'apertura, ma spread tra 15–50pt erodono il profitto atteso.

---

## Appendice A: File del Progetto

| File | Descrizione |
|------|-------------|
| `EA_Pattern.mq5` | EA multi-pattern v2.02 |
| `pattern_mining.py` | Script Python per analisi pattern mining v3 |
| `Export_PAPP.mq5` | Script MQL5 per esportazione CSV D1 (legacy) |
| `PAPP_Export.csv` | Dataset D1 EURUSD 2009–2026 (4278 barre) |
| `PaPP_Median.ex5` | Indicatore personalizzato (compilato, in `MQL5/Indicators/`) |

## Appendice B: Glossario

| Termine | Definizione |
|---------|-------------|
| **Punto (pt)** | 0.00001 per EURUSD a 5 decimali. 10pt = 1 pip |
| **Pip** | 0.0001 per EURUSD. 1 pip = 10pt |
| **Sharpe Ratio** | Rapporto rendimento/rischio annualizzato. >1 = buono, >2 = ottimo |
| **Crossover** | Evento in cui il prezzo chiude OLTRE una media mobile dopo aver chiuso DALL'ALTRO LATO |
| **SL dinamico** | Stop-loss che segue l'evoluzione di una linea (es. MA365) |
| **Hard SL** | Ordine stop-loss inviato al broker all'apertura |
| **Risk‑% sizing** | Calcolo del lotto basato su una percentuale fissa di equity divisa per la distanza SL |
| **Walk-forward** | Tecnica di validazione: train su 70%, test su 30%, per simulare performance out-of-sample |
