# Script di export dati `Export_PAPP` — come funziona

> Documento di **solo funzionamento**: cosa fa lo script e cosa contiene il file che produce,
> in parole semplici. Riferimento codice: [Export_PAPP.mq5](Export_PAPP.mq5) (v2.04).

---

## In una frase

Legge i valori dell'indicatore `PHAI_Median` e li salva in un **file CSV**, **una riga per barra**.
Ogni riga contiene tutto ciò che serve per analizzare quel momento: prezzi, le 7 medie e la mediana,
quanto il prezzo è lontano da ogni linea, le 4 metriche del fascio, i **crossover**, e una serie di
"semafori" (flag) sulla struttura del fascio.

È il **ponte** tra l'indicatore (che vive sul grafico) e l'analisi automatica (il *miner* in Python
che cerca i pattern). L'indicatore mostra, l'export **registra in tabella**.

---

## 1. Cosa fa, passo per passo

1. **Carica l'indicatore** in modalità "a gradini" (valori D1 grezzi, non interpolati): così ogni
   valore è quello esatto della giornata e i crossover scattano solo a fine giornata, uguali su
   ogni timeframe.
2. **Legge dai buffer** dell'indicatore la mediana e le 7 medie.
3. Per **ogni barra** calcola un insieme di colonne derivate (distanze, flag, metriche, crossover).
4. **Scrive tutto nel CSV**, nell'intervallo di date richiesto.

---

## 2. Principio chiave: "sorgente unica"

Le medie usate per i crossover e per le metriche sono **le stesse** che finiscono nelle colonne
`MA365…MA3` del CSV (campionate dai buffer dell'indicatore, non ricalcolate con medie parallele).

Conseguenza: i crossover sono **coerenti per costruzione** con le colonne delle medie. Non può
succedere che il CSV dica "il prezzo ha tagliato la MA30" ma la colonna MA30 mostri un valore
diverso da quello usato per il confronto. Tutto viene dalla **stessa fonte**, ancorata al D1.

---

## 3. Le colonne del CSV, per gruppi

### a) Prezzo e linee
`datetime, open, high, low, close` — la candela.
`median, MA365, MA182, MA121, MA30, MA14, MA7, MA3` — la mediana e le 7 medie (gli stessi valori
dell'indicatore).

### b) Distanze dal prezzo (`dMed%`, `d365%` … `d3%`)
Quanto la **chiusura** è sopra/sotto ogni linea, in percentuale:
```
dXXX% = (close − linea) / linea × 100
```
`dMed%` è rispetto alla mediana, `d365%` rispetto alla MA365, e così via. Positivo = prezzo sopra
la linea, negativo = sotto.

### c) Posizione sopra/sotto (`a365` … `a3`, `aMed`)
Semafori 0/1: valgono **1 se il prezzo è SOPRA** quella linea, 0 se è sotto. Versione "sì/no" delle
distanze del punto (b).

### d) Struttura "veloci vs lente"
- `fastAvg` = media di (MA3, MA7, MA14) — le veloci.
- `slowAvg` = media di (MA121, MA182, MA365) — le lente.
- `spread` = `fastAvg − slowAvg` — è lo **Spread Frattale** (come nell'indicatore): positivo =
  veloci sopra le lente = struttura rialzista.
- `spreadVel` = variazione dello spread rispetto alla barra precedente (sta allargando o chiudendo).
- `orderScore` = da **−6 a +6**. Confronta le 6 coppie di medie adiacenti (MA3 vs MA7, MA7 vs MA14,
  …): **+1** se la più veloce sta sopra la più lenta, **−1** se sotto. Tutte ordinate dal veloce al
  lento = +6 = **ventaglio perfettamente ordinato al rialzo**; −6 = ordinato al ribasso; valori
  vicini a 0 = fascio intrecciato/confuso.
- `s14_30` = 1 se MA14 > MA30 ; `s7_30` = 1 se MA7 > MA30 (due flag rapidi di momentum).
- `longBelow` = 1 se **tutte e tre** le lente (365, 182, 121) sono **sotto** la mediana ;
  `longAbove` = 1 se tutte e tre sono **sopra**. Servono a capire se anche il fondo del trend è
  schierato da una parte.

### e) Le 4 metriche + i loro percentili
`cluster%, vel%, acc%, vol%` = il **valore della barra corrente** delle quattro metriche del fascio
(stesse formule dell'indicatore: vedi [INDICATORE_PHAI_Median.md](INDICATORE_PHAI_Median.md) §4).
`cluPct, velPct, accPct, volPct` = il **percentile** di ciascuna sulla finestra di **252 giornate**
(quanto è alta/bassa rispetto all'ultimo anno; per velocità e accelerazione il percentile è
sull'intensità, ignorando il segno).

### f) Crossover (`crossMA365` … `crossMA3`, `crossMed`)
Per ogni linea: **+1** se il prezzo ha tagliato la linea verso l'**alto**, **−1** se verso il
**basso**, **0** se nessun taglio in quella giornata. È l'informazione che usa l'EA per entrare a
mercato (vedi §4).

### g) Coppie linea-linea (`MA3_7`, `MA7_14` … `MA182_365`)
Semafori 0/1: valgono **1 se la media più veloce della coppia sta sopra la più lenta** (es. `MA3_7`
= 1 se MA3 > MA7). Quando uno di questi flag **cambia** da una riga all'altra, vuol dire che due
medie si sono **incrociate tra loro** (crossover linea-linea, diverso dal crossover prezzo-linea
del punto (f)).

---

## 4. Come sono calcolati i crossover (il cuore dell'export)

Un crossover prezzo-linea è il momento in cui la **chiusura giornaliera** passa da una parte
all'altra di una linea. Si confrontano **due giornate consecutive**:
```
Taglio verso l'ALTO  (+1): ieri close ≤ linea   E   oggi close > linea
Taglio verso il BASSO (−1): ieri close ≥ linea   E   oggi close < linea
nessun taglio              (0): negli altri casi
```
Due dettagli importanti:
- Si usano **chiusure e medie del giornaliero reale** (non valori interpolati), così il segnale è
  identico su qualunque timeframe.
- Il crossover viene segnato **una sola volta**, alla prima barra di ogni nuova giornata: non si
  ripete per ogni candela intraday.

La mediana ha il suo crossover (`crossMed`) calcolato allo stesso modo.

---

## 5. Coerenza con l'indicatore (v2.04)

Lo script è allineato all'indicatore in tutto:
- **medie e mediana**: stessi buffer (modalità a gradini);
- **cluster / velocità / accelerazione / volatilità**: stesse formule, e dalla v2.04 stessa
  semantica → `cluster` = valore della barra corrente, `vel`/`acc` **con segno**, più i percentili;
- **spread frattale**: stessa definizione (veloci − lente).

Quindi ciò che vedi nel pannello dell'indicatore e ciò che leggi nel CSV **parlano la stessa lingua**.

---

## 6. A cosa serve il file prodotto

- È l'**input del miner** (`pattern_mining.py`): ogni riga è una barra con tutte le sue
  caratteristiche, e il miner ci cerca i pattern e li valida.
- L'**EA non usa il CSV**: legge l'indicatore direttamente sul grafico. Il CSV serve all'analisi
  *offline*, non al trading in tempo reale.

---

## Riepilogo (una riga per gruppo di colonne)

| Gruppo | Cosa contiene |
|---|---|
| prezzo + linee | candela, mediana, 7 medie |
| `dXXX%` | distanza % del prezzo da ogni linea |
| `aXXX` | sopra/sotto ogni linea (0/1) |
| struttura | fastAvg, slowAvg, spread, spreadVel, orderScore, s14_30, s7_30, longBelow/Above |
| metriche | cluster/vel/acc/vol (valore) + cluPct/velPct/accPct/volPct (percentile su 1 anno) |
| `crossXXX` | crossover prezzo-linea: +1 su / −1 giù / 0 niente |
| `MAx_y` | coppie linea-linea: 1 se la veloce sta sopra la lenta |
