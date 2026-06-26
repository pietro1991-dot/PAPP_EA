# Pattern USDCHF — schede di validazione

> Generato da `genera_schede.py` · split **2020.01.01** · costi spread=15 comm=7.0 · portafoglio 1 posizione/volta.
> Numeri in **PUNTI** (1 pip = 10 punti). "Successi" = trade chiusi in profitto. TEST = out-of-sample (≥ split).

## Pattern dell'EA

| # | Pattern | Stato | TestN | Successi | Win% | PnL test | Ret/DD | PnL train |
|---|---|---|---|---|---|---|---|---|
| P1 | MA14 SELL → crossMA182 [TP=5000pt(500pip)] | ✅ ON | 48 | 19 | 40% | +23892 | 4.75 | +45686 |
| P2 | MA182 BUY → crossMA14 | ⬜ OFF | 41 | 14 | 34% | +3219 | 0.47 | +16883 |
| P3 | MA14 BUY [SL=MA121, TP=120pt(12pip)] | ✅ ON | 61 | 50 | 82% | +1735 | 0.95 | +704 |
| P4 | MA14 SELL → crossMA365 [TP=5000pt(500pip)] | ⬜ OFF | 27 | 12 | 44% | +14755 | 2.61 | +27112 |
| P5 | MA3 SELL → crossMA182 [TP=5000pt(500pip)] | ⬜ OFF | 55 | 20 | 36% | +7938 | 0.83 | +30400 |
| P6 | MA7 SELL → crossMA182 [TP=5000pt(500pip)] | ⬜ OFF | 53 | 20 | 38% | +13011 | 1.67 | +21355 |
| P7 | Median SELL → crossMA182 [TP=5000pt(500pip)] | ✅ ON | 55 | 17 | 31% | +27072 | 3.70 | +22949 |
| P8 | MA14 SELL → crossMA30 | ⬜ OFF | 85 | 24 | 28% | +12322 | 1.79 | +3024 |

## Schede

### P1 — MA14 SELL → crossMA182 [TP=5000pt(500pip)]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA182 · **Protezioni:** TP 5000 punti (500 pip)
- **Test OOS:** 48 trade, **19 successi (40%)**, PnL **+23892**, Ret/DD 4.75, MaxDD 5026
- **Train:** 64 trade, 32 successi (50%), PnL +45686

### P2 — MA182 BUY → crossMA14
*MA182 BUY -> crossMA14 [BUY-trend, 5/5, Ret/DD 1.88, +20237]*  
- **Stato:** OFF · **Direzione:** BUY · **Entrata:** cross prezzo×MA182
- **Uscita:** cross×MA14
- **Test OOS:** 41 trade, **14 successi (34%)**, PnL **+3219**, Ret/DD 0.47, MaxDD 6919
- **Train:** 54 trade, 21 successi (39%), PnL +16883

### P3 — MA14 BUY [SL=MA121, TP=120pt(12pip)]
- **Stato:** ON · **Direzione:** BUY · **Entrata:** cross prezzo×MA14
- **Uscita:** — · **Protezioni:** SL dinamico su MA121, TP 120 punti (12 pip)
- **Test OOS:** 61 trade, **50 successi (82%)**, PnL **+1735**, Ret/DD 0.95, MaxDD 1835
- **Train:** 104 trade, 87 successi (84%), PnL +704

### P4 — MA14 SELL → crossMA365 [TP=5000pt(500pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA365 · **Protezioni:** TP 5000 punti (500 pip)
- **Test OOS:** 27 trade, **12 successi (44%)**, PnL **+14755**, Ret/DD 2.61, MaxDD 5656
- **Train:** 64 trade, 28 successi (44%), PnL +27112

### P5 — MA3 SELL → crossMA182 [TP=5000pt(500pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA3
- **Uscita:** cross×MA182 · **Protezioni:** TP 5000 punti (500 pip)
- **Test OOS:** 55 trade, **20 successi (36%)**, PnL **+7938**, Ret/DD 0.83, MaxDD 9562
- **Train:** 73 trade, 38 successi (52%), PnL +30400

### P6 — MA7 SELL → crossMA182 [TP=5000pt(500pip)]
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA7
- **Uscita:** cross×MA182 · **Protezioni:** TP 5000 punti (500 pip)
- **Test OOS:** 53 trade, **20 successi (38%)**, PnL **+13011**, Ret/DD 1.67, MaxDD 7785
- **Train:** 69 trade, 33 successi (48%), PnL +21355

### P7 — Median SELL → crossMA182 [TP=5000pt(500pip)]
- **Stato:** ON · **Direzione:** SELL · **Entrata:** cross prezzo×Median
- **Uscita:** cross×MA182 · **Protezioni:** TP 5000 punti (500 pip)
- **Test OOS:** 55 trade, **17 successi (31%)**, PnL **+27072**, Ret/DD 3.70, MaxDD 7321
- **Train:** 69 trade, 27 successi (39%), PnL +22949

### P8 — MA14 SELL → crossMA30
*MA14 SELL -> crossMA30 [SELL exit veloce, Ret/DD 2.41]*  
- **Stato:** OFF · **Direzione:** SELL · **Entrata:** cross prezzo×MA14
- **Uscita:** cross×MA30
- **Test OOS:** 85 trade, **24 successi (28%)**, PnL **+12322**, Ret/DD 1.79, MaxDD 6876
- **Train:** 119 trade, 41 successi (34%), PnL +3024

## Appendice — candidati base robusti (positivi train E test)

> Tutti i pattern base (entry prezzo-linea; exit su cross **oppure** SL+TP) che restano in attivo sia su train sia su test. Ordinati per Ret/DD del test.

Candidati robusti: **47**

| Pattern | TestN | Successi | Win% | PnL test | Ret/DD |
|---|---|---|---|---|---|
| MA7 SELL SL=Median TP=100pt | 172 | 171 | 99% | +11055 | 4.84 |
| Median SELL SL=Median TP=150pt | 103 | 102 | 99% | +10773 | 4.72 |
| Median SELL SL=Median TP=120pt | 111 | 110 | 99% | +8497 | 3.72 |
| MA14 SELL → crossMA182 | 44 | 16 | 36% | +18909 | 3.57 |
| MA7 SELL SL=Median TP=80pt | 175 | 174 | 99% | +7809 | 3.42 |
| Median SELL SL=Median TP=100pt | 126 | 125 | 99% | +7467 | 3.27 |
| MA14 SELL SL=Median TP=100pt | 123 | 122 | 99% | +7233 | 3.17 |
| MA3 SELL SL=Median TP=100pt | 191 | 189 | 99% | +10079 | 2.65 |
| MA14 SELL SL=Median TP=120pt | 120 | 119 | 99% | +8324 | 2.49 |
| Median SELL SL=Median TP=80pt | 132 | 131 | 99% | +5315 | 2.33 |
| Median SELL → crossMA182 | 50 | 12 | 24% | +16458 | 2.25 |
| MA121 SELL → crossMA182 | 34 | 9 | 26% | +12172 | 2.08 |
| MA14 SELL SL=Median TP=150pt | 106 | 104 | 98% | +6852 | 2.05 |
| MA7 SELL → crossMA182 | 49 | 18 | 37% | +15036 | 1.93 |
| MA14 SELL → crossMA30 | 85 | 24 | 28% | +12322 | 1.79 |
| MA3 SELL → crossMA30 | 97 | 36 | 37% | +15556 | 1.72 |
| MA14 SELL → crossMA365 | 25 | 11 | 44% | +13507 | 1.62 |
| MA7 SELL → crossMA365 | 28 | 12 | 43% | +13834 | 1.49 |
| MA30 SELL SL=Median TP=150pt | 63 | 62 | 98% | +4598 | 1.38 |
| MA3 SELL → crossMA365 | 30 | 14 | 47% | +13256 | 1.35 |
| Median SELL → crossMA365 | 26 | 10 | 38% | +12510 | 1.29 |
| Median SELL SL=Median TP=60pt | 134 | 133 | 99% | +2771 | 1.21 |
| MA3 SELL → crossMA182 | 51 | 18 | 35% | +10723 | 1.12 |
| MA3 SELL SL=Median TP=150pt | 156 | 154 | 99% | +9491 | 0.98 |
| MA14 BUY SL=MA121 TP=120pt | 61 | 50 | 82% | +1735 | 0.95 |
| MA30 SELL → crossMA182 | 40 | 9 | 22% | +9811 | 0.94 |
| MA14 SELL → crossMA3 | 150 | 53 | 35% | +5958 | 0.92 |
| MA7 SELL → crossMA121 | 60 | 23 | 38% | +7017 | 0.82 |
| MA30 SELL → crossMA365 | 21 | 9 | 43% | +7017 | 0.73 |
| MA14 SELL → crossMA7 | 143 | 48 | 34% | +4968 | 0.72 |
| MA3 SELL SL=Median TP=120pt | 167 | 165 | 99% | +5949 | 0.61 |
| MA14 SELL → crossMA121 | 52 | 15 | 29% | +6151 | 0.58 |
| MA14 SELL → crossMA14 | 155 | 43 | 28% | +4611 | 0.58 |
| Median SELL → crossMA121 | 63 | 19 | 30% | +4806 | 0.51 |
| MA182 BUY → crossMA14 | 41 | 14 | 34% | +3219 | 0.47 |
| MA3 SELL → crossMA121 | 63 | 25 | 40% | +4997 | 0.46 |
| MA30 SELL → crossMA7 | 85 | 30 | 35% | +2089 | 0.43 |
| MA3 SELL → crossMA14 | 150 | 56 | 37% | +4674 | 0.39 |
| MA7 SELL SL=Median TP=120pt | 143 | 141 | 99% | +3597 | 0.38 |
| Median SELL → crossMA3 | 157 | 60 | 38% | +2599 | 0.30 |
