# Motore Reversione — Relative-Value Mean-Reversion sui Cross

Secondo motore PaPP, **concettualmente opposto al "Motore base _linea-prezzo"**:
- Il Motore base usa le **linee/feature** (MA, Mediana, Cluster/Vel/Accel/Vol) su singoli strumenti.
- Questo motore **NON usa le linee**: trada il **valore relativo** tra due valute correlate (reversione sul cross).

## L'idea (perché funziona)
Un cross di due valute **correlate e a fluttuazione libera** (es. EURGBP) oscilla in un range invece di trendare, perché il fattore comune (il dollaro) si cancella e resta solo il valore relativo, che mean-reverte. Su EURUSD da solo non funziona: c'è il trend del dollaro che travolge la reversione.

## Strategia (EA_RelVal_EURGBP.mq5)
Su **EURGBP, H6**:
1. `osc` = percentile (finestra 280) della distanza `(close - MA28)/MA28`.
2. **Entrata**: `osc < 10` → BUY ; `osc > 90` → SELL.
3. **Uscita**: `osc` torna a 50, oppure dopo 48 barre (MaxHold).
4. **Una posizione per volta.**
5. **Size**: % di balance (`PctCapitale`, compounding) × **vol-targeting** (size più piccola quando la volatilità è alta → rimpicciolisce gli anni-disastro tipo 2016).

### Config validata
`LoThr=10 HiThr=90 ExitLevel=50 MAPeriod=28 PctWindow=280 MaxHoldBars=48`
`VolTarget=true VolFast=40 VolSlow=2000 VolFloor=0.3 VolCap=2.5 PctCapitale=25`
`SafetySLpip=0 SARpip=0 TPlongPip=0 TPshortPip=0`

### Risultato backtest reale (IC Markets, EURGBP H6, 2010-2025, VolSlow=2000)
**+9.603€ su 10k (+96%)**, PF 1,17, 406 trade, win 64%, Recovery 1,38, Sharpe 0,38.
**DD bilancio 30,6% / equity 38,5%.** Anno peggiore 2016 = **−1.357€** (col vol-targeting; era −3.286 con VolSlow=480). ~12/16 anni positivi.
Per abbassare ancora il DD: ridurre PctCapitale (es. 12-15 → dimezza DD e rendimento).
(Versione precedente VolSlow=480: +8.855€, DD equity 50%, 2016 −3.286 — il fix VolSlow=2000 ha tagliato DD e 2016.)

## Cosa è stato TESTATO e BOCCIATO (non rifarlo)
- **Feature/linee come segnale**: nessun edge (15+ test). L'EA giustamente non le usa.
- **Stop-and-Reverse (SAR)**: peggiora (whipsaw). Logica corretta nel codice ma `SARpip=0`.
- **Stop loss secco**: peggiora (taglia le reversioni che tornano).
- **TP stretto**: alza il win% ma abbassa profitto/RDD (taglia i vincenti).
- **Filtri-trend** (Efficiency Ratio, Cluster, MEDIA, frattale): non generalizzano o rimuovono l'edge (edge=fade contro-trend, gli anni-trend sono il suo costo).
- **Mediana PaPP come riferimento** invece di MA28: il guadagno era look-ahead; pulita NON batte la MA28.
- **Estremi z>2.5 / "oltre il 100"**: rumore (né fade né follow), troppo rari → overfit.
- **Conviction-sizing** (lotto più grosso sugli estremi): amplifica il drawdown, non l'edge.

## Cosa FUNZIONA (validato train+test)
- Soglie **10/90** (più selettive di 20/80).
- **Vol-targeting con VolSlow lungo (2000)** → R/DD 4.5→5.5, 2016 −458→−273.

## Selezione nuovi simboli (famiglia cross) — l'edge NON è generico
TESTATO: l'edge **non si trasferisce** automaticamente ad altri cross "correlati". Ogni candidato
va verificato, e la maggior parte FALLISCE.
- **AUDNZD = BOCCIATO** (testato 2026-06-29, 17082 barre H6 reali): con config EURGBP perde
  (PF 0.89, R/DD −0.7), e a NESSUNA scala temporale (MA 28/60/100/150/200) regge train+test.
  Motivo: AU e NZ divergono (commodity/tassi diversi) → AUDNZD ha trend pluriennali (1.38→1.00→su)
  dove EURGBP oscilla. La "saggezza convenzionale" (AUDNZD più mean-reverting) NON regge ai dati.
- **EURCHF = BOCCIATO** (PF 1.13 vs EURGBP 1.57 + rischio de-peg SNB).
- Da provare con aspettative BASSE: AUDCAD, NZDCAD.
- **EVITARE**: CHF (SNB/de-peg), JPY (interventi/safe-haven), coppie contro USD (trend dollaro), esotici.
- **CONCLUSIONE: EURGBP è un edge RARO e speciale** (UK/Eurozona molto sincronizzate, cross
  arbitraggiato e range-bound). Per ora il Motore Reversione = SOLO EURGBP. Diversificare con
  altri cross è difficile: testare uno per uno, non assumere.

## Strumenti di ricerca/validazione
In `../Motore base _linea-prezzo/Indicatore/`: relval.py, relval_wf.py, relval_h1.py, relval_sar.py, relval_filter*.py, anatomy.py, tp_sl_grid.py, classifier.py, ecc.
Dati reali H6 EURGBP esportabili con Export_PAPP / Export_M1.
