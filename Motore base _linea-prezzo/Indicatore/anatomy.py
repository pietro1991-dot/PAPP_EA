#!/usr/bin/env python3
"""
anatomy.py - Anatomia ONESTA del trade di reversione "entro all'estremo, esco al centro".

Modello ESATTO dell'utente: oscillatore = percentile distanza prezzo-mediana.
  osc < lo -> BUY,  osc > hi -> SELL.
  ESCO quando l'oscillatore torna a 50 (reversione completata). Niente TP/SL
  artificiali: lascio che sia la reversione a chiudere. Cap di sicurezza max_hold.
Stampa la scomposizione: win%, vincitore medio, perdente medio, hold, e il NETTO,
per capire SE il problema e' "movimento < spread" o "perdenti grandi quanto i vincenti".
"""
import argparse
import numpy as np
import pandas as pd

PERIODS = [365, 182, 121, 30, 14, 7, 3]

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--win", type=int, default=250)
    ap.add_argument("--lo", type=float, default=20)
    ap.add_argument("--hi", type=float, default=80)
    ap.add_argument("--max-hold", type=int, default=500)
    ap.add_argument("--spread-pip", type=float, default=1.0)
    ap.add_argument("--train-pct", type=float, default=0.70)
    ap.add_argument("--exit-at", type=float, default=50, help="livello osc di uscita vincente (50=centro, 80=estremo opposto se compri sotto 20)")
    ap.add_argument("--stop-pip", type=float, default=0, help="stop in pip per tagliare i perdenti (0=nessuno)")
    return ap.parse_args()

def rolling_pct_signed(x, W):
    out = np.full(len(x), np.nan); need = max(20, W//4)
    for i in range(len(x)):
        lo = max(0, i-W+1); w = x[lo:i+1]
        if i+1-lo >= need: out[i] = 100.0*(w <= x[i]).mean()
    return out

def report(name, trades):
    if not trades:
        print(f"  {name}: nessun trade"); return
    pnl = np.array([t["pnl"] for t in trades])
    gross = np.array([t["gross"] for t in trades])
    hold = np.array([t["hold"] for t in trades])
    wins = pnl[pnl > 0]; losses = pnl[pnl < 0]
    aw = wins.mean() if len(wins) else 0.0
    al = losses.mean() if len(losses) else 0.0
    pf = wins.sum()/-losses.sum() if losses.sum() != 0 else float('inf')
    eq = np.cumsum(pnl); dd = (eq-np.maximum.accumulate(eq)).min()
    print(f"  {name}: N={len(pnl)}  win={ (pnl>0).mean()*100:4.0f}%  "
          f"vincMedio={aw:+5.1f}  perdMedio={al:+6.1f}  |mossa|media={np.abs(gross).mean():4.1f}pip")
    print(f"        EV/trade={pnl.mean():+5.2f}pip  totale={pnl.sum():+7.0f}pip  PF={pf:.2f}  "
          f"maxDD={dd:+6.0f}  holdMedio={hold.mean():4.0f}barre")

def main():
    a = parse_args()
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    close = df["close"]; mas = np.column_stack([close.rolling(p).mean() for p in PERIODS])
    median = np.median(mas, axis=1)
    c = close.to_numpy()
    osc = rolling_pct_signed((c-median)/median*100.0, a.win)
    n = len(df); split = int(n*a.train_pct)

    trades = []
    i = 0
    while i < n:
        o = osc[i]
        if np.isnan(o): i += 1; continue
        d = +1 if o < a.lo else (-1 if o > a.hi else 0)
        if d == 0: i += 1; continue
        entry = c[i]; j = i
        # uscita vincente: per BUY al livello exit_at (es. 50 o 80); per SELL specularmente (100-exit_at)
        tgt = a.exit_at if d == +1 else (100 - a.exit_at)
        for k in range(i+1, min(i+1+a.max_hold, n)):
            j = k
            move = (c[k]-entry)/pip*d
            if a.stop_pip > 0 and move <= -a.stop_pip:   # stop taglia il perdente
                break
            if np.isnan(osc[k]): continue
            if (d == +1 and osc[k] >= tgt) or (d == -1 and osc[k] <= tgt):
                break
        gross = (c[j]-entry)/pip*d
        trades.append(dict(exit_i=j, gross=gross, pnl=gross - a.spread_pip, hold=j-i))
        i = j + 1

    print(f"\n=== ANATOMIA REVERSIONE | {a.csv.split('/')[-1]} | entro <{a.lo}/>{a.hi}, esco a 50 ===")
    print(f"win={a.win} spread={a.spread_pip}pip maxHold={a.max_hold} barre={n}")
    report("TUTTO", trades)
    report("TRAIN", [t for t in trades if t["exit_i"] <  split])
    report("TEST ", [t for t in trades if t["exit_i"] >= split])
    print()

if __name__ == "__main__":
    main()
