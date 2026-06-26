# Pattern EURUSD — schede di validazione

> Generato da `genera_schede.py` · split **2020.01.01** · costi spread=15 comm=7.0 · portafoglio 1 posizione/volta.
> Numeri in **PUNTI** (1 pip = 10 punti). "Successi" = trade chiusi in profitto. TEST = out-of-sample (≥ split).

## Pattern dell'EA

| # | Pattern | Stato | TestN | Successi | Win% | PnL test | Ret/DD | PnL train |
|---|---|---|---|---|---|---|---|---|
| P1 | MA30 SELL [SL=MA365, TP=150pt(15pip)] | ✅ ON | 39 | 37 | 95% | +4473 | 18.79 | +7015 |
| P2 | MA121 BUY [SL=MA365, TP=150pt(15pip)] | ✅ ON | 25 | 22 | 88% | +2422 | 6.53 | +2835 |
| P3 | MA365 SELL [SL=MA121, TP=120pt(12pip)] | ✅ ON | 16 | 14 | 88% | +776 | 1.42 | +1151 |
| P4 | MA7 SELL [SL=MA365, TP=120pt(12pip)] | ✅ ON | 85 | 78 | 92% | +3660 | 2.00 | +6827 |
| P5 | MA30 BUY [SL=MA365, TP=150pt(15pip)] | ✅ ON | 43 | 38 | 88% | +2196 | 1.62 | +6780 |
| P6 | MA14 BUY [SL=MA365, TP=150pt(15pip)] | ✅ ON | 66 | 61 | 92% | +3017 | 1.00 | +4356 |
| P7 | MA3 SELL → crossMA121 [TP=1500pt(150pip)] | ⬜ OFF | 71 | 44 | 62% | +8414 | 0.61 | +16473 |
| P8 | MA7 SELL → crossMA121 [TP=1500pt(150pip)] | ⬜ OFF | 69 | 41 | 59% | +10344 | 0.85 | +19336 |
| P9 | MA14 SELL → crossMA121 [TP=1500pt(150pip)] | ⬜ OFF | 54 | 31 | 57% | +273 | 0.02 | -4377 |
| P10 | MA30 SELL → crossMA121 [TP=1500pt(150pip)] | ⬜ OFF | 45 | 24 | 53% | -4836 | -0.25 | +8776 |

## Schede

### P1 — MA30 SELL [SL=MA365, TP=150pt(15pip)]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA30
- **Uscita:** — · **Protezioni:** SL dinamico su MA365, TP 150 punti (15 pip)
- **Test OOS:** 39 trade, **37 successi (95%)**, PnL **+4473**, Ret/DD 18.79, MaxDD 238
- **Train:** 82 trade, 80 successi (98%), PnL +7015

### P2 — MA121 BUY [SL=MA365, TP=150pt(15pip)]
- **Stato:** ON · **Direzione:** BUY · **Entrata:** cross prezzo×MA121
- **Uscita:** — · **Protezioni:** SL dinamico su MA365, TP 150 punti (15 pip)
- **Test OOS:** 25 trade, **22 successi (88%)**, PnL **+2422**, Ret/DD 6.53, MaxDD 371
- **Train:** 40 trade, 37 successi (92%), PnL +2835

### P3 — MA365 SELL [SL=MA121, TP=120pt(12pip)]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA365
- **Uscita:** — · **Protezioni:** SL dinamico su MA121, TP 120 punti (12 pip)
- **Test OOS:** 16 trade, **14 successi (88%)**, PnL **+776**, Ret/DD 1.42, MaxDD 546
- **Train:** 20 trade, 19 successi (95%), PnL +1151

### P4 — MA7 SELL [SL=MA365, TP=120pt(12pip)]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA7
- **Uscita:** — · **Protezioni:** SL dinamico su MA365, TP 120 punti (12 pip)
- **Test OOS:** 85 trade, **78 successi (92%)**, PnL **+3660**, Ret/DD 2.00, MaxDD 1832
- **Train:** 155 trade, 145 successi (94%), PnL +6827

### P5 — MA30 BUY [SL=MA365, TP=150pt(15pip)]
- **Stato:** ON · **Direzione:** BUY · **Entrata:** cross prezzo×MA30
- **Uscita:** — · **Protezioni:** SL dinamico su MA365, TP 150 punti (15 pip)
- **Test OOS:** 43 trade, **38 successi (88%)**, PnL **+2196**, Ret/DD 1.62, MaxDD 1353
- **Train:** 56 trade, 55 successi (98%), PnL +6780

### P6 — MA14 BUY [SL=MA365, TP=150pt(15pip)]
- **Stato:** ON · **Direzione:** BUY · **Entrata:** cross prezzo×MA14
- **Uscita:** — · **Protezioni:** SL dinamico su MA365, TP 150 punti (15 pip)
- **Test OOS:** 66 trade, **61 successi (92%)**, PnL **+3017**, Ret/DD 1.00, MaxDD 3008
- **Train:** 82 trade, 76 successi (93%), PnL +4356

### P7 — MA3 SELL → crossMA121 [TP=1500pt(150pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA3
- **Uscita:** cross×MA121 · **Protezioni:** TP 1500 punti (150 pip)
- **Test OOS:** 71 trade, **44 successi (62%)**, PnL **+8414**, Ret/DD 0.61, MaxDD 13793
- **Train:** 148 trade, 93 successi (63%), PnL +16473

### P8 — MA7 SELL → crossMA121 [TP=1500pt(150pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA7
- **Uscita:** cross×MA121 · **Protezioni:** TP 1500 punti (150 pip)
- **Test OOS:** 69 trade, **41 successi (59%)**, PnL **+10344**, Ret/DD 0.85, MaxDD 12222
- **Train:** 134 trade, 86 successi (64%), PnL +19336

### P9 — MA14 SELL → crossMA121 [TP=1500pt(150pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA121 · **Protezioni:** TP 1500 punti (150 pip)
- **Test OOS:** 54 trade, **31 successi (57%)**, PnL **+273**, Ret/DD 0.02, MaxDD 14080
- **Train:** 99 trade, 57 successi (58%), PnL -4377

### P10 — MA30 SELL → crossMA121 [TP=1500pt(150pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA30
- **Uscita:** cross×MA121 · **Protezioni:** TP 1500 punti (150 pip)
- **Test OOS:** 45 trade, **24 successi (53%)**, PnL **-4836**, Ret/DD -0.25, MaxDD 19373
- **Train:** 84 trade, 52 successi (62%), PnL +8776

## Appendice — candidati base robusti (positivi train E test)

> Tutti i pattern base (entry prezzo-linea; exit su cross **oppure** SL+TP) che restano in attivo sia su train sia su test. Ordinati per Ret/DD del test.

Candidati robusti: **51**

| Pattern | TestN | Successi | Win% | PnL test | Ret/DD |
|---|---|---|---|---|---|
| MA30 SELL SL=MA365 TP=150pt | 39 | 37 | 95% | +4473 | 18.79 |
| MA30 SELL SL=MA365 TP=120pt | 39 | 37 | 95% | +3363 | 14.13 |
| MA365 SELL SL=MA121 TP=60pt | 18 | 17 | 94% | +596 | 11.92 |
| MA30 SELL SL=MA365 TP=100pt | 39 | 37 | 95% | +2623 | 11.02 |
| MA30 SELL SL=MA365 TP=80pt | 39 | 37 | 95% | +1883 | 7.91 |
| MA121 BUY SL=MA365 TP=150pt | 25 | 22 | 88% | +2422 | 6.53 |
| MA30 SELL SL=MA365 TP=60pt | 40 | 38 | 95% | +1181 | 4.96 |
| MA121 BUY SL=MA365 TP=120pt | 25 | 22 | 88% | +1762 | 4.75 |
| MA121 BUY SL=MA365 TP=100pt | 27 | 24 | 89% | +1478 | 3.98 |
| MA182 SELL → crossMA3 | 33 | 19 | 58% | +7519 | 3.93 |
| MA30 SELL SL=MA365 TP=50pt | 40 | 38 | 95% | +801 | 3.37 |
| MA7 SELL SL=MA365 TP=150pt | 82 | 75 | 91% | +5616 | 3.12 |
| MA121 BUY SL=MA365 TP=80pt | 27 | 24 | 89% | +998 | 2.69 |
| MA7 BUY SL=MA365 TP=120pt | 96 | 88 | 92% | +4753 | 2.18 |
| MA7 SELL SL=MA365 TP=120pt | 85 | 78 | 92% | +3660 | 2.00 |
| MA182 SELL SL=MA365 TP=100pt | 12 | 10 | 83% | +463 | 1.94 |
| MA7 SELL SL=MA365 TP=100pt | 85 | 79 | 93% | +3160 | 1.71 |
| MA30 BUY SL=MA365 TP=150pt | 43 | 38 | 88% | +2196 | 1.62 |
| MA7 BUY SL=MA365 TP=100pt | 98 | 90 | 92% | +3149 | 1.45 |
| MA365 SELL SL=MA121 TP=120pt | 16 | 14 | 88% | +776 | 1.42 |
| MA121 BUY SL=MA365 TP=60pt | 27 | 24 | 89% | +518 | 1.40 |
| MA7 BUY SL=MA365 TP=80pt | 99 | 92 | 93% | +2865 | 1.31 |
| MA365 SELL SL=MA121 TP=100pt | 18 | 16 | 89% | +652 | 1.19 |
| MA182 SELL SL=MA365 TP=80pt | 12 | 10 | 83% | +263 | 1.02 |
| MA14 BUY SL=MA365 TP=150pt | 66 | 61 | 92% | +3017 | 1.00 |
| MA7 SELL SL=Median TP=150pt | 131 | 130 | 99% | +7801 | 0.88 |
| MA7 SELL SL=MA365 TP=80pt | 86 | 80 | 93% | +1638 | 0.87 |
| MA30 BUY SL=MA365 TP=120pt | 44 | 39 | 89% | +1154 | 0.85 |
| MA7 SELL SL=Median TP=100pt | 153 | 152 | 99% | +5210 | 0.78 |
| MA121 BUY SL=MA365 TP=50pt | 27 | 24 | 89% | +278 | 0.75 |
| MA14 SELL SL=MA365 TP=150pt | 53 | 50 | 94% | +2373 | 0.68 |
| MA365 SELL → crossMA7 | 24 | 10 | 42% | +1981 | 0.63 |
| MA365 SELL SL=MA121 TP=80pt | 18 | 16 | 89% | +332 | 0.61 |
| MA7 SELL SL=Median TP=120pt | 137 | 136 | 99% | +4489 | 0.51 |
| MA14 BUY SL=MA365 TP=120pt | 69 | 64 | 93% | +1481 | 0.49 |
| MA7 SELL SL=Median TP=80pt | 161 | 160 | 99% | +2634 | 0.40 |
| MA3 BUY SL=MA365 TP=120pt | 138 | 119 | 86% | +1424 | 0.31 |
| MA365 BUY → crossMA365 | 27 | 3 | 11% | +2993 | 0.30 |
| MA3 BUY SL=MA365 TP=80pt | 154 | 137 | 89% | +1388 | 0.30 |
| MA30 BUY SL=MA365 TP=100pt | 44 | 39 | 89% | +374 | 0.28 |
