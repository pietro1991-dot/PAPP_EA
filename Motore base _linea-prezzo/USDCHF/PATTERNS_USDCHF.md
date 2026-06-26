# Pattern USDCHF — schede di validazione

> Generato da `genera_schede.py` · split **2020.01.01** · costi spread=20 comm=7.0 · portafoglio 1 posizione/volta.
> Numeri in **PUNTI** (1 pip = 10 punti). "Successi" = trade chiusi in profitto. TEST = out-of-sample (≥ split).

## Pattern dell'EA

| # | Pattern | Stato | TestN | Successi | Win% | PnL test | Ret/DD | PnL train |
|---|---|---|---|---|---|---|---|---|
| P1 | MA14 SELL → crossMA182 [TP=500pip] | ✅ ON | 48 | 19 | 40% | +23652 | 4.69 | +45366 |
| P2 | MA182 BUY → crossMA14 | ⬜ OFF | 41 | 14 | 34% | +3014 | 0.43 | +16613 |
| P3 | MA14 BUY [SL=MA121, TP=12pip] | ✅ ON | 61 | 50 | 82% | +1430 | 0.77 | +184 |
| P4 | MA14 SELL → crossMA365 [TP=500pip] | ⬜ OFF | 27 | 12 | 44% | +14620 | 2.56 | +26792 |
| P5 | MA3 SELL → crossMA182 [TP=500pip] | ⬜ OFF | 55 | 20 | 36% | +7663 | 0.79 | +30035 |
| P6 | MA7 SELL → crossMA182 [TP=500pip] | ⬜ OFF | 53 | 20 | 38% | +12746 | 1.62 | +21010 |
| P7 | Median SELL → crossMA182 [TP=500pip] | ✅ ON | 55 | 17 | 31% | +26797 | 3.62 | +22604 |
| P8 | MA14 SELL → crossMA30 | ⬜ OFF | 85 | 24 | 28% | +11897 | 1.71 | +2429 |

## Schede

### P1 — MA14 SELL → crossMA182 [TP=500pip]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA182 · **Protezioni:** TP 500 pip
- **Test OOS:** 48 trade, **19 successi (40%)**, PnL **+23652**, Ret/DD 4.69, MaxDD 5041
- **Train:** 64 trade, 32 successi (50%), PnL +45366

### P2 — MA182 BUY → crossMA14
*MA182 BUY -> crossMA14 [BUY-trend, 5/5, Ret/DD 1.88, +20237]*  
- **Stato:** OFF · **Direzione:** BUY · **Entrata:** cross prezzo×MA182
- **Uscita:** cross×MA14
- **Test OOS:** 41 trade, **14 successi (34%)**, PnL **+3014**, Ret/DD 0.43, MaxDD 7019
- **Train:** 54 trade, 21 successi (39%), PnL +16613

### P3 — MA14 BUY [SL=MA121, TP=12pip]
- **Stato:** ON · **Direzione:** BUY · **Entrata:** cross prezzo×MA14
- **Uscita:** — · **Protezioni:** SL dinamico su MA121, TP 12 pip
- **Test OOS:** 61 trade, **50 successi (82%)**, PnL **+1430**, Ret/DD 0.77, MaxDD 1865
- **Train:** 104 trade, 87 successi (84%), PnL +184

### P4 — MA14 SELL → crossMA365 [TP=500pip]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA365 · **Protezioni:** TP 500 pip
- **Test OOS:** 27 trade, **12 successi (44%)**, PnL **+14620**, Ret/DD 2.56, MaxDD 5716
- **Train:** 64 trade, 28 successi (44%), PnL +26792

### P5 — MA3 SELL → crossMA182 [TP=500pip]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA3
- **Uscita:** cross×MA182 · **Protezioni:** TP 500 pip
- **Test OOS:** 55 trade, **20 successi (36%)**, PnL **+7663**, Ret/DD 0.79, MaxDD 9677
- **Train:** 73 trade, 38 successi (52%), PnL +30035

### P6 — MA7 SELL → crossMA182 [TP=500pip]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA7
- **Uscita:** cross×MA182 · **Protezioni:** TP 500 pip
- **Test OOS:** 53 trade, **20 successi (38%)**, PnL **+12746**, Ret/DD 1.62, MaxDD 7885
- **Train:** 69 trade, 33 successi (48%), PnL +21010

### P7 — Median SELL → crossMA182 [TP=500pip]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×Median
- **Uscita:** cross×MA182 · **Protezioni:** TP 500 pip
- **Test OOS:** 55 trade, **17 successi (31%)**, PnL **+26797**, Ret/DD 3.62, MaxDD 7406
- **Train:** 69 trade, 27 successi (39%), PnL +22604

### P8 — MA14 SELL → crossMA30
*MA14 SELL -> crossMA30 [SELL exit veloce, Ret/DD 2.41]*  
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA30
- **Test OOS:** 85 trade, **24 successi (28%)**, PnL **+11897**, Ret/DD 1.71, MaxDD 6961
- **Train:** 119 trade, 41 successi (34%), PnL +2429

## Appendice — candidati base robusti (positivi train E test)

> Tutti i pattern base (entry prezzo-linea; exit su cross **oppure** SL+TP) che restano in attivo sia su train sia su test. Ordinati per Ret/DD del test.

Candidati robusti: **42**

| Pattern | TestN | Successi | Win% | PnL test | Ret/DD |
|---|---|---|---|---|---|
| Median SELL SL=Median TP=15pip | 103 | 102 | 99% | +10258 | 4.48 |
| MA7 SELL SL=Median TP=10pip | 172 | 171 | 99% | +10195 | 4.46 |
| MA14 SELL → crossMA182 | 44 | 16 | 36% | +18689 | 3.51 |
| Median SELL SL=Median TP=12pip | 111 | 110 | 99% | +7942 | 3.47 |
| MA7 SELL SL=Median TP=8pip | 175 | 174 | 99% | +6934 | 3.03 |
| Median SELL SL=Median TP=10pip | 126 | 125 | 99% | +6837 | 2.99 |
| MA3 SELL SL=Median TP=10pip | 191 | 189 | 99% | +9124 | 2.36 |
| MA14 SELL SL=Median TP=12pip | 120 | 119 | 99% | +7724 | 2.31 |
| Median SELL → crossMA182 | 50 | 12 | 24% | +16208 | 2.19 |
| Median SELL SL=Median TP=8pip | 132 | 131 | 99% | +4655 | 2.03 |
| MA121 SELL → crossMA182 | 34 | 9 | 26% | +12002 | 2.03 |
| MA14 SELL SL=Median TP=15pip | 106 | 104 | 98% | +6322 | 1.89 |
| MA7 SELL → crossMA182 | 49 | 18 | 37% | +14791 | 1.88 |
| MA14 SELL → crossMA30 | 85 | 24 | 28% | +11897 | 1.71 |
| MA14 SELL → crossMA365 | 25 | 11 | 44% | +13382 | 1.59 |
| MA7 SELL → crossMA365 | 28 | 12 | 43% | +13694 | 1.46 |
| MA3 SELL → crossMA365 | 30 | 14 | 47% | +13106 | 1.32 |
| MA30 SELL SL=Median TP=15pip | 63 | 62 | 98% | +4283 | 1.28 |
| Median SELL → crossMA365 | 26 | 10 | 38% | +12380 | 1.27 |
| MA3 SELL → crossMA182 | 51 | 18 | 35% | +10468 | 1.08 |
| MA30 SELL → crossMA182 | 40 | 9 | 22% | +9611 | 0.91 |
| MA3 SELL SL=Median TP=15pip | 156 | 154 | 99% | +8711 | 0.89 |
| MA14 SELL → crossMA3 | 150 | 52 | 35% | +5208 | 0.78 |
| MA7 SELL → crossMA121 | 60 | 23 | 38% | +6717 | 0.77 |
| MA14 BUY SL=MA121 TP=12pip | 61 | 50 | 82% | +1430 | 0.77 |
| MA30 SELL → crossMA365 | 21 | 9 | 43% | +6912 | 0.71 |
| MA14 SELL → crossMA7 | 143 | 48 | 34% | +4253 | 0.59 |
| MA14 SELL → crossMA121 | 52 | 15 | 29% | +5891 | 0.55 |
| MA3 SELL SL=Median TP=12pip | 167 | 165 | 99% | +5114 | 0.52 |
| Median SELL → crossMA121 | 63 | 19 | 30% | +4491 | 0.47 |
| MA14 SELL → crossMA14 | 155 | 43 | 28% | +3836 | 0.47 |
| MA182 BUY → crossMA14 | 41 | 14 | 34% | +3014 | 0.43 |
| MA3 SELL → crossMA121 | 63 | 25 | 40% | +4682 | 0.43 |
| MA30 SELL → crossMA7 | 85 | 30 | 35% | +1664 | 0.34 |
| MA3 SELL → crossMA14 | 150 | 56 | 37% | +3924 | 0.32 |
| MA7 SELL SL=Median TP=12pip | 143 | 141 | 99% | +2882 | 0.30 |
| Median SELL → crossMA14 | 102 | 40 | 39% | +3338 | 0.24 |
| MA3 SELL → crossMA7 | 219 | 82 | 37% | +2728 | 0.21 |
| MA7 BUY SL=Median TP=12pip | 124 | 123 | 99% | +1756 | 0.18 |
| Median SELL → crossMA7 | 133 | 49 | 37% | +1643 | 0.16 |
