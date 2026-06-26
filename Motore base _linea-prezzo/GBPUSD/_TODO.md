# GBPUSD — stato

- [x] **1. Esporta dati**: `PAPP_Export_GBPUSD.csv` presente (export da MT5 su grafico GBPUSD D1).
- [x] **2. Valida i pattern** (walk-forward + costi): `analisi_oos.txt` generato.
      ```
      python3 ../Indicatore/pattern_mining.py PAPP_Export_GBPUSD.csv \
              --spread=20 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
      # walk-forward robusto:
      python3 ../Indicatore/pattern_mining.py PAPP_Export_GBPUSD.csv \
              --robust --folds=5 --spread=20 --commission=7
      ```
- [x] **3. Imposta i pattern** validati in `EA_GBPUSD.mq5` (MOTORE BASE, 3 pattern, tutti ON).
- [ ] **4. Compila e backtesta** in MetaEditor/MT5 sul grafico GBPUSD.

## Pattern impostati (v2.10, MOTORE BASE)

Motore base = identico a EURUSD: solo entry crossover prezzo-linea + exit su
linea specifica / SL dinamico + TP. Ogni pattern ha `InpPx_On` per attivarlo.

Selezionati da SCANSIONE ESAUSTIVA (848 pattern base, 14 superstiti OOS),
ordinati per RISCHIO/RENDIMENTO (Ret/DD test), uno per ingresso, dir diversificata.
Con STOP LOSS validato (v2.11):
- P1 MA182 SELL -> exit crossMA3,  SL=MA121 (linea)    <- SL migliora: OOS Ret/DD 2.31->3.34
- P2 MA365 SELL -> exit crossMA7,  SL fisso 500 pip    <- disaster stop (linee peggiorano)
- P3 MA121 BUY  -> exit crossMA30, SL fisso 500 pip    <- taglia la coda -7282 -> -5027

STOP LOSS - nuovo input `InpPx_SLpips` (disaster stop a distanza fissa, usato se SL=0).
Proiezione portafoglio (entry al close, costi spread20+comm7):
                N     Tot      OOS     MaxDD   Worst
  senza SL    205   +40109   +25764   10717   -7282
  con SL      180   +48227   +26737    9584   -5027   <- meglio su TUTTO
Co-beneficio: P2/P3 ora dimensionano su 500 pip REALI (non il fallback finto 100 pip)
-> sizing corretto. Vedi scratchpad/sl_test.py.

> SCOPERTA: nessun pattern SL+TP (TP-stretto/SL-largo) prezzo-linea sopravvive OOS
> su GBPUSD (0 su ~720 candidati). E l'USCITA conta: uscire su linea VELOCE (MA3/MA7)
> da' Ret/DD molto migliore che su linea lenta (MA121). I 14 superstiti sono tutti
> a cross; deduplicati per ingresso restano ~7 segnali. Edge modesto (Sharpe 0.02-0.14).
> I pattern linea-linea (XMA…) e OPP del miner NON sono qui: servirebbe il motore esteso.
> Scansione: scratchpad/base_scan.py (riusa pattern_mining).
