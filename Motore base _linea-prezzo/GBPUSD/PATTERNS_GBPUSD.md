# Pattern GBPUSD — schede di validazione

> Generato da `genera_schede.py` · split **2020.01.01** · costi spread=20 comm=7.0 · portafoglio 1 posizione/volta.
> Numeri in **PUNTI** (1 pip = 10 punti). "Successi" = trade chiusi in profitto. TEST = out-of-sample (≥ split).

## Pattern dell'EA

| # | Pattern | Stato | TestN | Successi | Win% | PnL test | Ret/DD | PnL train |
|---|---|---|---|---|---|---|---|---|
| P1 | MA182 SELL → crossMA3 [SL=MA121] | ✅ ON | 24 | 12 | 50% | +11822 | 3.34 | +7932 |
| P2 | MA365 SELL → crossMA7 [SLfix=500pip] | ✅ ON | 27 | 11 | 41% | +6007 | 1.11 | +8808 |
| P3 | MA121 BUY → crossMA30 [SLfix=500pip] | ✅ ON | 32 | 13 | 41% | +8908 | 1.78 | +4750 |

## Schede

### P1 — MA182 SELL → crossMA3 [SL=MA121]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA182
- **Uscita:** cross×MA3 · **Protezioni:** SL dinamico su MA121
- **Test OOS:** 24 trade, **12 successi (50%)**, PnL **+11822**, Ret/DD 3.34, MaxDD 3540
- **Train:** 22 trade, 12 successi (55%), PnL +7932

### P2 — MA365 SELL → crossMA7 [SLfix=500pip]
*MA365 SELL -> crossMA7, disaster stop 500pip*  
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA365
- **Uscita:** cross×MA7 · **Protezioni:** disaster stop 500 pip
- **Test OOS:** 27 trade, **11 successi (41%)**, PnL **+6007**, Ret/DD 1.11, MaxDD 5428
- **Train:** 34 trade, 15 successi (44%), PnL +8808

### P3 — MA121 BUY → crossMA30 [SLfix=500pip]
*MA121 BUY -> crossMA30, disaster stop 500pip*  
- **Stato:** ON · **Direzione:** BUY · **Entrata:** cross prezzo×MA121
- **Uscita:** cross×MA30 · **Protezioni:** disaster stop 500 pip
- **Test OOS:** 32 trade, **13 successi (41%)**, PnL **+8908**, Ret/DD 1.78, MaxDD 4998
- **Train:** 41 trade, 15 successi (37%), PnL +4750

## Appendice — candidati base robusti (positivi train E test)

> Tutti i pattern base (entry prezzo-linea; exit su cross **oppure** SL+TP) che restano in attivo sia su train sia su test. Ordinati per Ret/DD del test.

Candidati robusti: **25**

| Pattern | TestN | Successi | Win% | PnL test | Ret/DD |
|---|---|---|---|---|---|
| MA182 SELL → crossMA3 | 34 | 15 | 44% | +10849 | 2.31 |
| MA365 BUY → crossMA182 | 18 | 7 | 39% | +14468 | 1.98 |
| MA365 SELL → crossMA3 | 28 | 11 | 39% | +7801 | 1.96 |
| MA121 BUY → crossMA30 | 32 | 13 | 41% | +8908 | 1.78 |
| MA121 BUY → crossMA182 | 24 | 8 | 33% | +8423 | 1.63 |
| MA182 SELL → crossMA365 | 20 | 8 | 40% | +13939 | 1.15 |
| MA365 SELL → crossMA7 | 27 | 11 | 41% | +6007 | 1.11 |
| MA182 SELL → crossMA182 | 35 | 8 | 23% | +7458 | 0.74 |
| MA121 SELL → crossMA3 | 45 | 17 | 38% | +5880 | 0.69 |
| MA30 SELL → crossMA121 | 33 | 14 | 42% | +7467 | 0.66 |
| MA14 BUY SL=Median TP=6pip | 136 | 135 | 99% | +1718 | 0.63 |
| MA182 SELL → crossMA7 | 33 | 13 | 39% | +4452 | 0.58 |
| MA30 BUY SL=Median TP=8pip | 82 | 81 | 99% | +1556 | 0.57 |
| MA182 SELL → crossMA121 | 24 | 8 | 33% | +6483 | 0.56 |
| MA121 SELL → crossMA365 | 19 | 7 | 37% | +4916 | 0.38 |
| MA182 SELL → crossMA14 | 29 | 12 | 41% | +1945 | 0.23 |
| MA121 BUY → crossMA14 | 36 | 18 | 50% | +1041 | 0.22 |
| MA7 SELL → crossMA365 | 29 | 13 | 45% | +2521 | 0.22 |
| MA14 BUY SL=Median TP=5pip | 146 | 145 | 99% | +598 | 0.22 |
| MA7 SELL → crossMA14 | 138 | 56 | 41% | +3005 | 0.13 |
| MA3 SELL → crossMA365 | 30 | 13 | 43% | +1419 | 0.12 |
| MA121 SELL → crossMA121 | 47 | 8 | 17% | +1573 | 0.12 |
| MA30 BUY SL=Median TP=6pip | 86 | 85 | 99% | +68 | 0.02 |
| MA121 SELL → crossMA7 | 43 | 14 | 33% | +236 | 0.02 |
| MA121 BUY SL=Median TP=10pip | 39 | 38 | 97% | +37 | 0.01 |
