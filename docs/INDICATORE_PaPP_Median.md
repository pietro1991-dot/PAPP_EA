# Indicatore `PaPP_Median` — Documentazione tecnica precisa

> Riferimento sorgente: [src/symbols/indicators/PaPP_Median.mq5](../src/symbols/indicators/PaPP_Median.mq5)
> Versione 2.00 · indicatore *chart window* · 12 buffer · 8 plot.
>
> Questo documento descrive **solo l'indicatore**: cosa calcola, come, con quali
> formule, e cosa disegna. NON descrive l'EA né la generazione di ordini.

---

## 1. Principio cardine: ancoraggio al D1

**Tutti** i calcoli dell'indicatore sono eseguiti su dati **D1 (giornalieri)**, a
prescindere dal timeframe del grafico su cui è applicato (`#define ANCHOR_TF PERIOD_D1`).

Conseguenza diretta: la linea Mediana e le 7 medie hanno **lo stesso identico valore
su M5, M15, H1, H4, D1…** Cambia solo il *rendering* dentro la giornata (vedi §5),
non il valore calcolato. È il motivo per cui un EA che legge questo indicatore dà gli
stessi segnali su qualunque timeframe.

---

## 2. Input (parametri)

| Input | Default | Significato |
|---|---|---|
| `FontSize` | 9 | dimensione testo del pannello |
| `Smooth` | true | true = linea interpolata (liscia) intraday; false = a gradini (step D1) |
| `ShowMA` | true | mostra/nasconde le 7 medie |
| `ShowPanel` | true | mostra/nasconde il pannello informativo |
| `PanelBg` | C'20,20,25' | colore sfondo pannello |
| `InpSignals` | false | true = forza output **raw a gradini** (per rilevare crossover su qualsiasi TF) |
| `MAPeriod1..7` | 365,182,121,30,14,7,3 | periodi delle 7 medie, **in GIORNI di calendario** |

Costanti interne:
- `KSLOPE = 5` → ritardo (in barre D1) per velocità e accelerazione.
- `NVOL = 14` → finestra (barre D1) per la volatilità.
- `CLWIN = 252` → finestra storica (~1 anno di barre D1) per i percentili.

---

## 3. Le 7 medie mobili (MA)

Sette **medie mobili semplici (SMA) sulla chiusura D1**:

```
MA = iMA(symbol, PERIOD_D1, periodoInBarre, 0, MODE_SMA, PRICE_CLOSE)
```

I periodi sono espressi in **giorni di calendario** e convertiti in **numero di barre D1**
dalla funzione `TimeToBars(d)` ([righe 61-70](../src/symbols/indicators/PaPP_Median.mq5#L61)):
conta quante barre D1 reali cadono nei `d` giorni di calendario (così "365 giorni"
≈ ~250-260 barre di trading, non 365). Il periodo reale viene **ricorretto** man mano
che la history si completa (`SyncMAHandles`, [righe 278-291](../src/symbols/indicators/PaPP_Median.mq5#L278)):
serve quando il grafico è appena aperto e la storia D1 è ancora incompleta.

| Indice | Periodo | Colore | Etichetta |
|---|---|---|---|
| MA[0] | 365 g | DodgerBlue | lentissima (~1 anno) |
| MA[1] | 182 g | DeepSkyBlue | |
| MA[2] | 121 g | Turquoise | |
| MA[3] | 30 g  | LimeGreen | |
| MA[4] | 14 g  | Orange | |
| MA[5] | 7 g   | Tomato | |
| MA[6] | 3 g   | Red | velocissima |

---

## 4. La linea **Mediana** (il calcolo centrale, plot principale)

Per ogni barra D1, la **Mediana** è la **mediana statistica delle 7 MA** in quel punto
(`MedOf7`, [righe 157-162](../src/symbols/indicators/PaPP_Median.mq5#L157); `MedArr`,
[righe 137-145](../src/symbols/indicators/PaPP_Median.mq5#L137)):

1. si prendono i 7 valori MA validi della barra;
2. si ordinano;
3. **mediana** = valore centrale (se dispari) oppure media dei due centrali (se pari).

È quindi una linea centrale **robusta** del fascio di medie (resistente agli outlier,
a differenza della media aritmetica). Disegnata in **oro, spessore 2** (`PLOT_LABEL = "PaPP Median"`).

---

## 5. Ancoraggio D1 + rendering intraday (smooth vs raw)

Su un grafico **D1** la linea usa direttamente il valore della barra D1.

Su un grafico **sotto-D1** (es. M5) ogni candela intraday riceve un valore così:
- **Smooth = true** (default): valore **interpolato linearmente** tra la barra D1
  corrente e la precedente, in base alla frazione di tempo trascorsa nella giornata
  (`Interp`, [righe 265-270](../src/symbols/indicators/PaPP_Median.mq5#L265); `frac` calcolata
  a [riga 376](../src/symbols/indicators/PaPP_Median.mq5#L376)). Risultato: linea **liscia**.
- **Smooth = false** oppure **`InpSignals = true`**: valore **raw a gradini** — il valore
  D1 resta costante per tutta la giornata e "scatta" al cambio giorno
  ([righe 382-384](../src/symbols/indicators/PaPP_Median.mq5#L382)).

**Perché conta il raw/step:** i crossover (prezzo che taglia una linea) devono avvenire
**solo ai confini D1** ed essere identici su ogni timeframe. La modalità raw garantisce
questo. È la modalità usata da chi rileva i crossover (export/EA).

---

## 6. I 12 buffer

| # | Buffer | Tipo | Contenuto |
|---|---|---|---|
| 0 | `Buff_Median` | DATA (plot, oro) | linea Mediana |
| 1-7 | `gMA[0..6]` | DATA (plot) | le 7 MA (365…3) |
| 8 | `Buff_Cluster` | CALCULATIONS | metrica Cluster (solo valore corrente in `[0]`) |
| 9 | `Buff_Vel` | CALCULATIONS | metrica Velocità |
| 10 | `Buff_Acc` | CALCULATIONS | metrica Accelerazione |
| 11 | `Buff_Vol` | CALCULATIONS | metrica Volatilità |

I buffer 8-11 non sono disegnati: espongono il **valore corrente** delle 4 metriche
(per lettura da EA/script). I valori storici delle metriche vivono nella cache interna
`g_cache`, non nei buffer.

---

## 7. Le 4 metriche del fascio di MA (su finestra `CLWIN = 252` barre D1)

Calcolate in `RefreshMetricCache` ([righe 188-262](../src/symbols/indicators/PaPP_Median.mq5#L188)).
Per ognuna si ottiene il **valore corrente** e il suo **percentile** (`PctlOf`) rispetto
alla storia di 252 barre — così si sa se è alta o bassa storicamente.

### 7.1 Cluster (`cluster%`) — quanto è stretto il fascio
Per ogni barra: dispersione media delle 7 MA dalla loro mediana:
```
cluster = media_m( |MA_m - mediana| / mediana * 100 )
```
**Basso** = MA ammassate (fascio stretto, fase di compressione). **Alto** = MA divaricate.

### 7.2 Velocità (`vel%`) — pendenza del fascio (CON segno, da v2.01)
Variazione % di ogni MA su `KSLOPE = 5` barre D1, poi mediana delle 7:
```
vel = mediana_m( (MA_m[j] - MA_m[j+5]) / MA_m[j+5] * 100 )      // valore CON segno
```
**Segno +** = fascio in salita, **−** = in discesa. Il **percentile** (`velPct`),
che dà la "forza" (lieve/moderata/forte) nel pannello, è invece calcolato sulla
**magnitudine** `|vel|` rispetto alla storia di 252 barre. Quindi: il *segno* dà la
direzione, il *percentile* dà l'intensità.

> Nota v2.01: prima il valore corrente era salvato con `MathAbs` (sempre ≥0), e il
> pannello mostrava sempre "in salita". Corretto: ora `velCur` conserva il segno;
> solo l'array per il percentile resta in magnitudine.

### 7.3 Accelerazione (`acc%`) — derivata seconda (CON segno, da v2.01)
Differenza finita del secondo ordine su `KSLOPE`, poi mediana:
```
acc = mediana_m( (MA_m[j] - 2*MA_m[j+5] + MA_m[j+10]) / MA_m[j+10] * 100 )   // CON segno
```
**+** = la velocità sta aumentando (in accelerazione), **−** = sta calando (in
decelerazione). Come per la velocità, il percentile usa la magnitudine `|acc|`.

### 7.4 Volatilità (`vol%`) — rumore del fascio
Per ogni MA, deviazione standard dei rendimenti barra-su-barra su `NVOL = 14` barre D1;
poi mediana delle 7:
```
vol = mediana_m( stddev_{14}( (MA_m[t] - MA_m[t+1]) / MA_m[t+1] * 100 ) )
```
**Bassa** = fascio liscio/stabile. **Alta** = fascio mosso.

---

## 8. Distance (`Dist`) — posizione del prezzo rispetto alla Mediana

```
distPct = (bid - mediana) / mediana * 100
```
Quanto il prezzo corrente è **sopra/sotto** la Mediana, in %. Il suo valore assoluto è
percentilato su un istogramma di 252 distanze storiche (`distHist`,
[righe 250-261](../src/symbols/indicators/PaPP_Median.mq5#L250)).
Colore: **rosso** se sopra, **verde** se sotto. Il pannello annota: **"Sopra=SELL | Sotto=BUY"**.

---

## 9. Spread Frattale — fascio veloce vs fascio lento

Due "squadre" di medie ([righe 240-248](../src/symbols/indicators/PaPP_Median.mq5#L240)):
```
Veloce (fv) = (MA3 + MA7 + MA14) / 3
Lenta  (sv) = (MA365 + MA182 + MA121) / 3      (MA30 esclusa)
spread      = fv - sv
spreadVel   = spread(oggi) - spread(ieri)
```
- `spread > 0` → **BULLISH** (fascio veloce sopra il lento).
- `spread < 0` → **BEARISH**.
- `spreadVel` = velocità/variazione dello spread (sta allargando o chiudendo).

---

## 10. Pannello e tag (solo su grafici NON-D1)

Su D1 l'indicatore disegna solo le linee. Su timeframe inferiori, se `ShowPanel`,
mostra un pannello (`DrawInfo`, [righe 425-483](../src/symbols/indicators/PaPP_Median.mq5#L425)) con:
Mediana · Dist · Cluster · Velocità · Accelerazione · Volatilità · Frattale · i 7 valori MA
· l'hint "Sopra=SELL | Sotto=BUY". I valori numerici sono tradotti in parole
(`MagWord`/`DirWord`/`DistWord`, es. "molto stretto", "in salita forte", "molto sopra")
in base al percentile. `DrawTags` ([righe 504-513](../src/symbols/indicators/PaPP_Median.mq5#L504))
mette le etichette (Mediana + 7 MA) al bordo destro del grafico.

---

## 11. Cosa l'indicatore NON fa (importante)

- **Non genera ordini né segnali di trading.** L'hint "Sopra=SELL/Sotto=BUY" è solo
  testo nel pannello.
- **Non rileva esso stesso i crossover.** Espone i valori (Mediana, 7 MA, 4 metriche,
  Frattale) e, in modalità raw, i valori a gradini. Il **rilevamento dei crossover**
  (prezzo che taglia una linea, o linea che taglia linea) è fatto da chi legge
  l'indicatore — lo script di export e l'EA — non dall'indicatore.

---

## 12. In sintesi (una frase per livello)

- **Cosa disegna:** 7 SMA della chiusura D1 (3→365 giorni) + la loro **Mediana** (linea oro).
- **Come:** tutto calcolato su D1 e ancorato al D1 → identico su ogni timeframe; intraday
  solo interpolato (liscio) o a gradini (raw).
- **Cosa "trova":** lo **stato del fascio di medie** — quanto è stretto (Cluster), in che
  direzione va (Velocità), se accelera (Accelerazione), quanto è mosso (Volatilità), dove
  sta il prezzo rispetto al centro (Distance) e se i veloci dominano i lenti (Frattale) —
  ciascuno con il suo **percentile storico** su ~1 anno.
