# USDCHF — stato

- [x] **1. Esporta dati**: `PAPP_Export_USDCHF.csv` (D1, 2009.12.31 -> 2026.06.19, 4278 barre).
      (Nota: esiste anche `PAPP_Export_USDCHF_H1.csv`, export H1 a parte — NON usato per
       la pipeline D1; tenuto solo per eventuale analisi intraday.)
- [x] **2. Valida i pattern**: `analisi_oos.txt` generato.
      ```
      python3 ../Indicatore/pattern_mining.py PAPP_Export_USDCHF.csv \
              --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
      python3 ../Indicatore/pattern_mining.py PAPP_Export_USDCHF.csv \
              --robust --folds=5 --spread=15 --commission=7
      ```
- [x] **3. Crea `EA_USDCHF.mq5`** (MOTORE BASE, come EURUSD). 2 pattern, tutti ON.
- [ ] **4. Compila e backtesta** in MetaEditor/MT5 sul grafico USDCHF.

## Pattern impostati (v2.11, MOTORE BASE)

Da SCANSIONE ESAUSTIVA (848 base, 22 superstiti OOS), ordinati per Ret/DD test,
de-correlati (un rappresentante fast-SELL + un BUY di stile diverso):
- P1 MA14 SELL   -> crossMA182          (test +18076, Ret/DD 3.41)  <- migliore
- P2 Median SELL -> crossMA182          (test +14837, Ret/DD 2.03)
- P3 MA14 BUY, SL=MA121, TP=120         (test +1735, win 82%)  <- unico BUY, GRID

INSIGHT: su USDCHF le uscite migliori sono LENTE (crossMA182), al contrario di
GBPUSD (uscite veloci). L'edge e' concentrato in SELL (forza CHF).

STOP LOSS (validato, sl_test_chf.py): su P1/P2 NESSUNO stop aiuta - le linee
distruggono il pattern, il disaster stop fisso taglia profitto o peggiora i gap.
Worst -6173 (617 pip) e' modesto e irriducibile -> P1/P2 restano SENZA stop.
P3 tiene SL=MA121+TP (GRID gia' protetto).

SIZING: P1/P2 senza SL -> InpFallbackRiskPips alzato 100 -> 600 (escursione reale)
cosi' il lotto e' corretto senza piazzare uno stop. InpRiskPct=10 (come GBP).

v2.14 - TAKE PROFIT sui pattern SELL (ricerca su griglia TP 0..2000 pip):
- Su MA14 SELL->crossMA182, un TP~500 pip MIGLIORA total E OOS E Ret/DD, e
  DE-CONCENTRA il profitto (da 1 mega-trade a 0, win 43%->46%, piu' trade).
  Robusto su 4 date di split (TP500 batte TP0 su 2015/2017/2019; pari nel 2021).
- Meccanismo: chiudi a +500 e RIENTRI al prossimo cross -> cavalchi il trend a
  pezzi invece di un trade enorme che restituisce. Risolve la fragilita' "83% in
  2 mesi" e batte anche il trailing stop in OOS -> il TP=500 SOSTITUISCE il trail.
- Applicato a P1 e a tutte le varianti SELL (P4-P7). P2 (BUY, exit veloce) e P3
  (GRID) invariati. P8 (exit veloce) senza TP.
- Caveat: nel periodo piu' recente (2021+) il no-TP fa marginalmente meglio
  (trend lisci 2022-23). Da confermare nel backtest MT5 completo.

v2.13 - TUTTI i pattern base meritevoli (8 slot). Ricerca piu' approfondita:
exhaustive scan (split 2020) + walk-forward 5 finestre. I 22 superstiti collassano
in 3 BET distinti (le correlazioni entrate lo confermano):
  ON (de-correlati):
    P1 MA14 SELL  -> crossMA182 +trail   [SELL-trend, 5/5, Ret/DD 6.57]
    P2 MA182 BUY  -> crossMA14            [BUY-trend, 5/5, Ret/DD 1.88, +20237] <- NUOVO, forte
    P3 MA14 BUY, SL=MA121, TP=120         [BUY mean-revert, win 82%]
  OFF (robusti ma CORRELATI alla famiglia SELL - attivabili per test):
    P4 MA14 SELL  -> crossMA365 +trail    [5/5]
    P5 MA3 SELL   -> crossMA182 +trail    [5/5]
    P6 MA7 SELL   -> crossMA182 +trail    [5/5]
    P7 Median SELL-> crossMA182 +trail    [Ret/DD 2.03]
    P8 MA14 SELL  -> crossMA30            [exit veloce, Ret/DD 2.41]
NOTA CRITICA: i SELL-variant sono la STESSA scommessa di P1 (entry 56-76% overlap).
Attivarli tutti = sovraesposizione, non diversificazione. P2/P3 sono i veri
diversificatori (BUY). I pattern su MA14 fanno whipsaw (cross up/down 70% entro 3 barre).

--- precedente ---
v2.12 - RIDUZIONE GIVE-BACK (dopo backtest: equity sale poi restituisce ~meta'):
- P2 (Median SELL) DISATTIVATO: e' lo stesso pattern di P1 (76% overlap entro 3 barre,
  48% stessa barra) -> raddoppiava la stessa scommessa e il give-back. Tengo solo MA14.
- TRAILING PROFIT su P1: nuovo input InpPx_TrailAct/TrailGive. Quando il trade e'
  >= TrailAct pip in profitto, lo stop traila a TrailGive pip dal picco (ratchet).
  Default 500/500 (validato: tiene tutti i mega-trade, Ret/DD 6.96 -> 9.44).
  Blocca il picco invece di restituirlo aspettando il lento crossMA182.
- NIENTE stop di equity a livello conto: validato controproducente (uno stop al 10%
  scatta nel 2016 e fa perdere tutti i trend successivi; il give-back 19% e' il prezzo
  per restare dentro ai trend rari, che sono l'edge).
- ATTENZIONE RISCHIO: al 10% il conto era saltato nel 2010 (margin call). Per il backtest
  completo serve InpRiskPct basso (1-2%): l'edge sono pochi trend rari, devi sopravvivere
  alle lunghe magre per incassarli.

v2.15 - FIX UNITA' TP: InpP1_TP (e P4-P7) da 500 a 5000.
  Il TP nell'EA e' in PUNTI (tpPt*point), non in pip: 500 punti = 50 pip (10x troppo
  stretto). Il tp_test era validato a 500 PIP -> servono 5000 punti. Il GRID P3 (TP=120
  punti = 12 pip) e i TP di EURUSD erano gia' corretti. Da ri-backtestare USDCHF.
