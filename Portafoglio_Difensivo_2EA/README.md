# Portafoglio DIFENSIVO — 2 EA (entry, il più semplice)

Il pacchetto d'ingresso: solo i due EA più solidi e a basso drawdown, uno per
"stile" (trend + reversione). Poche cose, curva tranquilla.

## Risultato misurato (backtest reali, 16 anni)
- **CAGR ~10% / anno · Max Drawdown ~12.5%**
- Solo 2 grafici da gestire. Ideale per chi inizia.

## I 2 EA e la quota (già preimpostata)

| EA | File | Simbolo | Size validata | **QuotaConto** |
|----|------|---------|---------------|----------------|
| Base (trend) | `EA_EURUSD.mq5` | EUR/USD | RiskPct 12 | **48** |
| Reversione | `EA_RelVal_EURGBP.mq5` | EUR/GBP | PctCapitale 25 | **52** |

I valori di `QuotaConto` sono già impostati (risk-parity 48/52). Non tocchi altro.

## Installazione
1. Copia i 2 `.mq5` in `MQL5/Experts/` e **ricompila (F7)**.
2. Dipendenze: `PaPP_Median.ex5` in `MQL5/Indicators/`, `papp_push.mqh` in `MQL5/Include/`.
3. Ogni EA sul grafico del suo simbolo, **stesso conto**. Le quote sono già a posto.

## La scala dei pacchetti
- **Difensivo (2 EA, questo)** — DD ~12.5% — il più semplice.
- **Bilanciato / Trio (3 EA)** — DD ~11.5%.
- **Completo / Core-5 (5 EA)** — DD ~10.3% — il più stabile.
