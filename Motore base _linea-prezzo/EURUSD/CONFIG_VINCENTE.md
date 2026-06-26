# EURUSD — Configurazione canonica (solo P1-P6)

Backtest MT5 del **2026-06-26** (deposito 10.000 €, EURUSD D1, 2010.01.01 → 2025.12.31,
broker MetaQuotes-Demo, leva 1:33). Indicatore `PaPP_Median` **v2.02** (post-fix history-jitter).

Questi valori sono i **default attuali** di [EA_EURUSD.mq5](EA_EURUSD.mq5). Config scelta per il
**miglior profilo di rischio** (la variante con P8 faceva più profitto ma drawdown doppio).

## Risultato

| Metrica | Valore |
|---|---|
| Net Profit | **+92.236,81 €** (balance finale 102.236) |
| Trade totali | 783 · Win rate **96,9%** (759/783) |
| **Profit Factor** | **2.34** |
| **Recovery Factor** | **4.63** |
| Max Drawdown balance | 10.954 € (**10,80%**) |
| Max Drawdown equity | 19.940 € (**19,86%**) |

## Input generali

| Input | Valore |
|---|---|
| InpRiskPct | 12 |
| InpLotFixed | 0 |
| InpMaxLot | 5 |
| InpMaxSpread | 0 |
| InpMinSLDistPts | 50 |
| InpFallbackRiskPips | 500 |
| InpDynamicSL | true |
| InpMaxPos | 0 |
| InpMaxPerPattern | 0 |
| InpMagic | 20260623 |

## Pattern attivi

| Pattern | On | Entry | Dir | Exit | SL | TP |
|---|---|---|---|---|---|---|
| P1 | ✅ | MA30 | SELL | — | MA365 | 150 |
| P2 | ✅ | MA121 | BUY | — | MA365 | 150 |
| P3 | ✅ | MA365 | SELL | — | MA121 | 120 |
| P4 | ✅ | MA7 | SELL | — | MA365 | 120 |
| P5 | ✅ | MA30 | BUY | — | MA365 | 150 |
| P6 | ✅ | MA14 | BUY | — | MA365 | 150 |
| P7-P10 | ❌ | — | — | cross MA121 | 0 (no SL) | 1500 |

**Tutti e soli i pattern con SL su linea.** I pattern senza SL (P7-P10) sono OFF: portavano
più profitto ma quasi tutto il drawdown (vedi variante con P8: DD equity 34% vs 20% qui).

## Note

- Profilo TP-stretto / SL-largo (MA365): win rate alto, le poche perdite sono più grosse.
  Ma con solo i pattern stoppati il sistema è molto più sano (PF 2.34, Recovery 4.63).
- Bug indicatore risolto in v2.02: prima i backtest si "fermavano" al 2016 perché
  `PaPP_Median` andava "MA not ready" su ogni barra.

## File collegati

- Export trade: [papp_backtest_EURUSD.csv](papp_backtest_EURUSD.csv) (anche in `backtests/`, importato nel chatbot)
- Report MT5 completo: `backtests/ReportTester_EURUSD_soloP1-P6_2026-06-26/` (HTML + XLSX + grafici)
- Analisi per anno/mese: `backtests/ANALISI_EURUSD.md`
