# GBPUSD — Configurazione backtest (run 2026-06-26)

Backtest MT5 del **2026-06-26** (deposito 10.000 €, GBPUSD D1, broker MetaQuotes-Demo).
Indicatore `PaPP_Median` v2.02. EA in **PIP** (tutti gli input distanza uniformati a pip).

Questi valori sono i **default attuali** di [EA_GBPUSD.mq5](EA_GBPUSD.mq5).

## Risultato

| Metrica | Valore |
|---|---|
| Net Profit | **+34.758 €** (balance finale ~44.758) |
| Trade totali | 197 · Win rate **43,65%** (86/197) |
| Profit Factor | 1.46 |
| Recovery Factor | 5.10 |
| Max Drawdown balance | 6.017 € (**59,74%**) |
| Max Drawdown equity | 6.814 € (**63,96%**) |

> ⚠️ **Drawdown altissimo (64% equity).** Avviene presto, su conto ancora piccolo, con
> `RiskPct=15` (aggressivo). Profilo **trend-following**: win rate basso (44%) ma vincite
> grosse (PF 1.46). È redditizio ma **molto volatile** — valuta di abbassare il rischio.

## Input generali

| Input | Valore |
|---|---|
| InpRiskPct | 15 |
| InpMaxLot | 1.0 |
| InpMaxSpreadPips | 0 |
| InpMinSLDistPips | 5 |
| InpFallbackRiskPips | 500 |
| InpDynamicSL | true |
| InpMaxPos | 0 |
| InpMaxPerPattern | 0 |
| InpMagic | 20260624 |

## Pattern attivi (tutti ON) — distanze in PIP

| Pattern | Entry | Dir | Exit | SL linea | SLpips (disaster) | TP |
|---|---|---|---|---|---|---|
| P1 | MA182 | SELL | cross MA3 | MA121 | 100 pip | 200 pip |
| P2 | MA365 | SELL | cross MA7 | — | 100 pip | 200 pip |
| P3 | MA121 | BUY | cross MA30 | — | 100 pip | 200 pip |

Tutti **trend-following** (entrata su cross, uscita su cross opposto) con **disaster stop
100 pip** e **TP cap 200 pip**.

## File collegati

- Export trade: [papp_backtest_GBPUSD.csv](papp_backtest_GBPUSD.csv) (anche in `backtests/`, importato nel chatbot)
- Report MT5 completo: `backtests/ReportTester_GBPUSD_2026-06-26/` (HTML + XLSX + grafici + equity csv)
- Analisi per anno/mese: `backtests/ANALISI_GBPUSD.md`
