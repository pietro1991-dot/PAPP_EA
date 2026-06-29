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

### Risultato backtest reale (IC Markets, EURGBP H6, 2010-2025)
+8.855€ su 10k (+88,5%), PF 1,20, 399 trade, win 65%. DD equity ~50% (da abbassare con PctCapitale più basso). Edge: ~14/17 anni positivi.

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

## Selezione nuovi simboli (famiglia cross)
Servono: due valute **molto correlate** + **a fluttuazione libera** + liquide.
- ⭐ **AUDNZD** = candidato n.1 (il cross più mean-reverting; da testare).
- Buoni: AUDCAD, NZDCAD.
- **EVITARE**: cross col **CHF** (SNB lo gestisce; rischio de-peg — testato, EURCHF PF 1.13 vs EURGBP 1.57), cross col **JPY** (interventi BoJ, safe-haven), coppie contro **USD** (trend del dollaro), esotici.

## Strumenti di ricerca/validazione
In `../Motore base _linea-prezzo/Indicatore/`: relval.py, relval_wf.py, relval_h1.py, relval_sar.py, relval_filter*.py, anatomy.py, tp_sl_grid.py, classifier.py, ecc.
Dati reali H6 EURGBP esportabili con Export_PAPP / Export_M1.
