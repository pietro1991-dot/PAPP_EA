# USDCHF — stato

- [x] **1. Esporta dati**: `PAPP_Export_USDCHF.csv` (D1, 2009.12.31 -> 2026.06.19, 4278 barre).
      (Nota: esiste anche `PAPP_Export_USDCHF_H1.csv`, export H1 a parte — NON usato per
       la pipeline D1; tenuto solo per eventuale analisi intraday.)
- [x] **2. Valida i pattern**: `analisi_oos.txt` generato.
      ```
      python3 ../analysis/pattern_mining.py PAPP_Export_USDCHF.csv \
              --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
      python3 ../analysis/pattern_mining.py PAPP_Export_USDCHF.csv \
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
