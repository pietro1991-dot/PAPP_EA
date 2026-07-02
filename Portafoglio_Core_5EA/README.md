# Portafoglio CORE — 5 EA (il più stabile)

La composizione con il **miglior rendimento per unità di rischio** di tutto il parco.
Costruita con **risk-parity** (ogni EA pesa in base al rischio, non al capitale) e un
**core su EUR/USD** (il gioiello).

## Risultato misurato (backtest reali, 16 anni)

- **CAGR ~11.9% / anno · Max Drawdown ~10.3% · C/DD 1.16**
- Batte il trio (DD 15.1%) e ogni singolo EA. Stabile train (<2018) e test (>=2018).

## I pesi (quota di CAPITALE per ogni EA)

| EA | File | Simbolo | **Peso** | Su conto da 10.000 € |
|----|------|---------|----------|----------------------|
| Base (trend) | `EA_EURUSD.mq5` | EUR/USD | **50%** | 5.000 € |
| Reversione | `EA_RelVal_EURGBP.mq5` | EUR/GBP | **19%** | 1.900 € |
| Base (trend) | `EA_USDCHF.mq5` | USD/CHF | **15%** | 1.500 € |
| Reversione | `EA_RelVal_GBPCHF.mq5` | GBP/CHF | **9%** | 900 € |
| Base (trend) | `EA_GBPUSD.mq5` | GBP/USD | **7%** | 700 € |

> EUR/USD fa da **cuore** (metà del capitale). Gli altri 4 sono **satelliti** a peso
> piccolo: diversificano senza portare il loro drawdown. GBP/USD entra nonostante il
> suo DD alto perché è **anti-correlato a EUR/USD (−0.26)** → copertura pura.

## Perché i pesi sono così diversi (NON equal-weight)

Peso uguale di capitale ≠ peso uguale di rischio. Gli EA volatili (GBP/CHF, GBP/USD)
a parità di capitale si prendono troppo rischio. **Si pesa per 1/volatilità**: al più
mosso dai meno soldi. Ecco perché GBP/USD e GBP/CHF stanno bassi (7–9%) e EUR/USD
alto (50%).

## Come impostare i pesi — con l'input `QuotaConto` (semplicissimo)

Questi EA (versione portafoglio) hanno un input in più: **`QuotaConto`** = la % del
conto che quell'EA può usare. **Un solo conto, non tocchi le size validate**
(RiskPct / PctCapitale restano quelli): imposti solo la quota su ognuno.

| EA | Size validata (non toccare) | **QuotaConto da mettere** |
|----|------------------------------|---------------------------|
| EA_EURUSD | RiskPct 12 | **50** |
| EA_RelVal_EURGBP | PctCapitale 25 | **19** |
| EA_USDCHF | RiskPct 4 | **15** |
| EA_RelVal_GBPCHF | PctCapitale 25 | **9** |
| EA_GBPUSD | RiskPct 7 | **7** |

Ogni EA sizza come se avesse solo la sua fetta del conto (es. EUR/USD usa il 50%,
GBP/USD il 7%), pur stando tutti sullo stesso conto.

**Vantaggio doppio**: siccome la quota è una % del balance VIVO, il portafoglio
**compounda** e **si ribilancia da solo** — i pesi restano fissi automaticamente,
niente ribilanciamento manuale.

> Gli EA ORIGINALI (fuori da questa cartella) restano intatti, senza `QuotaConto`,
> per l'uso come singoli. Questa cartella è la versione "gruppo".

## Installazione

1. Copia i 5 `.mq5` in `MQL5/Experts/` e **ricompila (F7)** — hanno il nuovo input `QuotaConto` (i `.ex5` vanno rigenerati).
2. Dipendenze: `PaPP_Median.ex5` in `MQL5/Indicators/`, `papp_push.mqh` in `MQL5/Include/`.
3. Metti ogni EA sul grafico del suo simbolo, **stesso conto per tutti**, e imposta `QuotaConto` come in tabella (50/19/15/9/7).

## Quando preferire questo al trio
- **Trio (3 EA)**: più semplice, DD ~11.5% con risk-parity. Meno grafici da gestire.
- **Core (5 EA, questo)**: DD ~10.3%, CAGR più alto, ma 5 grafici + ribilancio. Massima stabilità.
