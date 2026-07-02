# Portafogli EA — quali far girare insieme (drawdown & profitto)

> Guida pratica per combinare gli EA. Il principio: **NON far girare un EA da solo**.
> I drawdown dei singoli sono alti; combinati si compensano perché guadagnano in
> regimi di mercato diversi. Le size si calibrano per bilanciare il rischio.

## I 5 EA del parco (numeri validati)

| EA | Motore | Logica | Net (16y) | PF | **DD singolo** | Profilo |
|----|--------|--------|-----------|----|----------------|---------|
| **EUR/USD** | Base | Trend / crossover (P1–P6) | +92.236 € | 2.34 | **~20%** | 🟢 il più solido |
| **GBP/USD** | Base | Trend-following (3 pattern) | +34.758 € | 1.46 | **~64%** | 🔴 aggressivo, DD alto |
| **USD/CHF** | Base | Trend (P1+P7, edge sottile) | modesto | ~1.2 | alto | 🟡 il più debole |
| **EUR/GBP** | Reversione | Fade distanza dalla media | +110% | 1.25 | **~21%** | 🟢 reversione pura, win ~79% |
| **GBP/CHF** | Reversione | Fade distanza dalla media | +258% | ~1.2 | **~54%** | 🔴 alto rendimento e DD (rischio franco) |

## Il principio della diversificazione

I due motori sono **decorrelati per costruzione**:

- **Motore Base = trend-following** → guadagna quando il mercato *si muove in direzione*.
- **Motore Reversione = mean-reversion** → guadagna quando il mercato *rientra / oscilla*.

Quando uno soffre (mercato che gli è ostile), l'altro tende a guadagnare. Per questo
**un EA Base + un EA Reversione insieme** è la combinazione che abbassa di più il
drawdown a parità di profitto. Dentro lo stesso motore, invece, aggiungere simboli
diversi (EUR/USD + GBP/USD…) diversifica *meno* ma comunque aiuta.

## ⭐ Il portafoglio raccomandato (DD combinato MISURATO)

Unendo le equity reali dei report (2010–2025, ribilanciato, correlazioni ~0):

| Composizione | Net | **DD combinato reale** |
|---|---|---|
| EUR/USD + EUR/GBP + GBP/CHF, equal-weight | +377% | 15.1% |
| **EUR/USD + EUR/GBP + GBP/CHF, GBP/CHF a metà size** | **+385%** | **🟢 11.3%** |

Il DD combinato (11.3%) è **più basso di tutti e tre i singoli** (19.5% / 21.1% / 53.7%):
il 53.7% di GBP/CHF, nel portfolio, si schiaccia a 11.3%. Correlazioni mensili
misurate: EURUSD/EURGBP **0.00**, EURUSD/GBPCHF **−0.01**, EURGBP/GBPCHF **−0.08**
(praticamente scollegati → massima diversificazione).

**Questo è il terzetto da vendere.** Se dovessi tenere solo alcune combinazioni, tieni queste 3.

## Portafogli consigliati

### 🟢 CONSERVATIVO — DD più basso (consigliato per iniziare)
Solo i due EA più solidi, uno per motore.

| EA | Motore | Size (PctCapitale) |
|----|--------|--------------------|
| EUR/USD | Base | piena |
| EUR/GBP | Reversione | 25 |

→ Due DD ~20% che **non coincidono nel tempo** → il DD combinato atteso resta
sotto il singolo. È il cuore "difensivo" del parco.

### 🟡 BILANCIATO — più profitto, DD ancora controllato
Aggiungi un secondo simbolo per motore, con size ridotta sui rischiosi.

| EA | Motore | Size consigliata |
|----|--------|------------------|
| EUR/USD | Base | piena |
| GBP/USD | Base | **ridotta** (DD 64%: dimezza la size) |
| EUR/GBP | Reversione | 25 |
| GBP/CHF | Reversione | **12** (metà: rischio-coda del franco) |

→ 2 motori × 2 simboli. GBP/USD e GBP/CHF portano profitto ma a size intera
sballano il DD: vanno **dimezzati**.

### 🔴 COMPLETO — tutti e 5 (massima diversificazione)
Il portfolio pieno. Solo se accetti un DD di picco più alto in cambio del
rendimento massimo e della curva più liscia nel lungo periodo.

| EA | Motore | Size consigliata |
|----|--------|------------------|
| EUR/USD | Base | piena |
| GBP/USD | Base | ridotta |
| USD/CHF | Base | ridotta (edge sottile: tienilo leggero) |
| EUR/GBP | Reversione | 25 |
| GBP/CHF | Reversione | 12 |

## Regole di size (per tenere il DD in riga)

1. **Mai size intera sui DD alti**: GBP/USD (64%) e GBP/CHF (54%) vanno a size
   ridotta/dimezzata, altrimenti dominano il drawdown di tutto il portfolio.
2. **EUR/USD e EUR/GBP** sono le fondamenta a size piena (DD ~20%).
3. **USD/CHF** è il più debole: tienilo leggero o escludilo se vuoi un parco snello.
4. Il capitale va **diviso** tra gli EA (non full-size su ciascuno): con N EA,
   ognuno lavora su ~1/N del conto.

## Cosa NON mettere insieme (o affatto)

- ❌ **Reversione sui MAJORS** (EUR/USD, GBP/USD, USD/CHF su H1): testata e
  **bocciata** — a costo reale perde (GBP/USD PF 0.82, DD 84%). Non fa parte del parco.
- ⚠️ Due EA **dello stesso motore sullo stesso tipo di coppia** (es. due GBP)
  diversificano poco: i loro DD tendono a coincidere.

---
*Nota: i DD combinati non si sommano — si compensano parzialmente perché i motori
guadagnano in regimi diversi. I DD in tabella sono dei SINGOLI a piena size; nel
portfolio, con le size calibrate qui sopra, il picco combinato è più basso.*
