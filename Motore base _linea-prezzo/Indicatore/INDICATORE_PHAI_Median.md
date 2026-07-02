# Indicatore `PHAI_Median` — come funziona

> Documento di **solo funzionamento**: cosa calcola l'indicatore e cosa significa,
> in parole semplici. Niente dettagli su colori, pannello o disegno.
> Riferimento codice: [PHAI_Median.mq5](PHAI_Median.mq5) (v2.01).

---

## In una frase

L'indicatore prende **7 medie mobili** del prezzo (da 3 giorni a 1 anno), ne calcola la
**mediana** (una "linea centrale" del trend), e poi misura **6 grandezze** che descrivono
lo *stato* di questo gruppo di medie. **Tutto è calcolato sul grafico giornaliero (D1).**

Immagina le 7 medie come un **ventaglio**: dalle stecche corte (medie veloci) a quelle
lunghe (medie lente). L'indicatore descrive com'è questo ventaglio: quanto è aperto, in
che direzione si muove, se accelera, quanto è stabile, e dov'è il prezzo rispetto al centro.

---

## 1. Il principio chiave: tutto è "ancorato" al giornaliero (D1)

Qualunque sia il timeframe del grafico (M5, H1, H4, D1…), **i calcoli usano sempre le barre
giornaliere**. Conseguenza pratica: la linea e i valori sono **identici su ogni timeframe**.
Mettere l'indicatore su M5 o su D1 dà gli stessi numeri; cambia solo quanto è "liscia" la
linea dentro la giornata, non il suo valore.

> Perché esiste anche una modalità "a gradini" (raw): per rilevare i **crossover** (il prezzo
> che taglia una linea) servono valori che cambiano **solo a fine giornata** e uguali su ogni
> timeframe. È la modalità usata da chi legge l'indicatore (script di export ed EA).

---

## 2. Le 7 medie mobili

Sono 7 **medie mobili semplici** (SMA) calcolate sulla **chiusura giornaliera**. I periodi
sono in **giorni di calendario**, convertiti automaticamente nel numero di barre D1 reali
(così "365 giorni" ≈ ~250 barre di trading, non 365):

| Media | Periodo | Tipo |
|---|---|---|
| MA365 | ~1 anno | lentissima |
| MA182 | ~6 mesi | lenta |
| MA121 | ~4 mesi | lenta |
| MA30 | ~1,5 mesi | media |
| MA14 | ~2-3 settimane | veloce |
| MA7 | ~1 settimana | veloce |
| MA3 | ~3 giorni | velocissima |

Le veloci reagiscono subito ai movimenti recenti; le lente rappresentano il trend di fondo.
La distanza tra veloci e lente racconta la "salute" del trend.

---

## 3. La linea Mediana — la linea principale

Per ogni giornata, la **Mediana** è il **valore centrale delle 7 medie**: si ordinano i 7
valori e si prende quello in mezzo (o la media dei due centrali).

È una "linea centrale robusta" del ventaglio. Si usa la **mediana** e non la media aritmetica
perché la mediana **non si lascia influenzare dai valori estremi**: se una media veloce schizza
via per un movimento improvviso, la mediana resta stabile e rappresentativa del grosso del fascio.

In pratica: la Mediana è il **baricentro del trend** secondo questo gruppo di medie.

---

## 4. Le 4 metriche sullo stato del fascio

Queste quattro grandezze descrivono *come si comporta* il ventaglio di medie. Per ognuna
l'indicatore fornisce **due informazioni**:

1. il **valore di oggi**;
2. il suo **percentile** rispetto all'ultimo anno (252 giornate).

> **Cosa vuol dire il percentile (importante).** Risponde alla domanda: *"questo valore, rispetto
> all'ultimo anno, è alto o basso?"* Un percentile dell'80% significa "più alto dell'80% delle
> giornate dell'ultimo anno" (cioè è tra i valori alti). Serve a dare **contesto**: 0,1% di
> dispersione è tanto o poco? Dipende dalla storia — il percentile lo dice.

### 4.1 Cluster — quanto è **compatto** il fascio
Misura quanto sono **vicine tra loro** le 7 medie: la distanza media di ciascuna media dalla
mediana, in percentuale.
```
cluster = media( |ogni MA − mediana| / mediana × 100 )
```
- **Basso** → medie ammassate, ventaglio **chiuso** (le velocità di trend si assomigliano:
  fase di compressione/indecisione, spesso prima di un movimento).
- **Alto** → medie molto distanti, ventaglio **aperto** (trend ampio e disteso).

### 4.2 Velocità — quanto **e in che direzione** si muove il fascio
La variazione percentuale di ogni media negli ultimi **5 giorni**, di cui si prende la mediana.
È un valore **con segno**:
```
velocità = mediana( (MA_oggi − MA_di_5_giorni_fa) / MA_di_5_giorni_fa × 100 )
```
- **Segno +** → il fascio sta **salendo**; **segno −** → sta **scendendo**.
- Il **percentile** (calcolato sull'intensità, ignorando il segno) dice **quanto forte** è il
  movimento rispetto all'ultimo anno: lieve, moderato o forte.

In breve: il **segno** dà la direzione, il **percentile** dà la forza.

### 4.3 Accelerazione — se il movimento **sta accelerando o rallentando**
È la "variazione della velocità" (la derivata seconda), sempre sui 5 giorni, mediana delle 7.
Valore **con segno**:
```
accelerazione = mediana( (MA_oggi − 2×MA_5gg_fa + MA_10gg_fa) / MA_10gg_fa × 100 )
```
- **Segno +** → la velocità sta **aumentando** (il movimento prende forza).
- **Segno −** → la velocità sta **calando** (il movimento si sta esaurendo).
- Il percentile (sull'intensità) dice quanto è marcata questa accelerazione.

### 4.4 Volatilità — quanto è **nervoso** il fascio
Per ogni media si misura quanto "ballano" i suoi rendimenti giornalieri negli ultimi **14 giorni**
(deviazione standard), e si prende la mediana delle 7.
```
volatilità = mediana( deviazione_standard_14gg dei rendimenti giornalieri di ogni MA )
```
- **Bassa** → medie lisce e stabili (movimento ordinato).
- **Alta** → medie mosse e irregolari (movimento confuso/rumoroso).

---

## 5. Distanza dal centro — dov'è il prezzo rispetto alla Mediana

Quanto il prezzo attuale è **sopra o sotto** la linea centrale, in percentuale:
```
distanza = (prezzo − mediana) / mediana × 100
```
- **Positiva** → prezzo **sopra** la mediana.
- **Negativa** → prezzo **sotto** la mediana.

Anche qui c'è il **percentile** dell'intensità: dice se l'attuale lontananza dal centro è
normale o eccezionale rispetto all'ultimo anno (utile per capire se il prezzo è "tirato"
lontano dal baricentro).

---

## 6. Spread Frattale — le medie veloci battono le lente?

Confronta due "squadre" di medie:
```
Squadra Veloce = media di (MA3, MA7, MA14)
Squadra Lenta  = media di (MA365, MA182, MA121)      (la MA30 resta fuori, è "di mezzo")

spread = Squadra Veloce − Squadra Lenta
```
- **spread > 0** → le veloci stanno **sopra** le lente → struttura **rialzista** (BULLISH).
- **spread < 0** → le veloci stanno **sotto** le lente → struttura **ribassista** (BEARISH).

Viene calcolata anche la **velocità dello spread** (spread di oggi − spread di ieri): dice se
il vantaggio di una squadra sull'altra **sta aumentando o si sta chiudendo** — cioè se il
momentum si rafforza o si indebolisce.

---

## 7. Cosa l'indicatore **NON** fa

- **Non genera ordini né segnali di acquisto/vendita.** Si limita a calcolare e descrivere lo
  stato del fascio di medie.
- **Non rileva da solo i crossover.** Fornisce i valori (Mediana, 7 medie, le metriche, lo
  spread); il **confronto "prezzo che taglia una linea"** è fatto da chi usa l'indicatore (lo
  script di export e l'EA), leggendone i valori.

---

## Riepilogo (una riga per concetto)

| Grandezza | Risponde alla domanda | Segno? |
|---|---|---|
| **Mediana** | dov'è il baricentro del trend? | — |
| **Cluster** | quanto è compatto il fascio di medie? | no (sempre ≥0) |
| **Velocità** | quanto e in che direzione si muove il fascio? | **sì** (+su / −giù) |
| **Accelerazione** | il movimento accelera o rallenta? | **sì** (+acc / −dec) |
| **Volatilità** | quanto è nervoso/irregolare il fascio? | no (sempre ≥0) |
| **Distanza** | quanto è lontano il prezzo dal centro? | **sì** (+sopra / −sotto) |
| **Spread Frattale** | le medie veloci dominano le lente? | **sì** (+rialzo / −ribasso) |

E per ognuna (tranne Mediana e Spread) c'è il **percentile**: *"rispetto all'ultimo anno,
questo valore è alto o basso?"*
