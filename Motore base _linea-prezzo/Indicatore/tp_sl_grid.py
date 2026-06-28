#!/usr/bin/env python3
"""
tp_sl_grid.py - Progetto dell'EA: entrata su distanza prezzo-mediana + griglia TP/SL.

Entrata (reversione, "entro con le linee"):
  oscillatore = percentile con segno della distanza close-mediana (7 MA, periodi
  in barre del TF) su finestra W.
  osc < lo  -> BUY   (prezzo molto sotto la mediana, attendo ritorno su)
  osc > hi  -> SELL  (prezzo molto sopra)
Uscita: TP o SL (decisi bar-per-bar coi massimi/minimi REALI; se nello stesso bar
  scattano entrambi conta SL = ipotesi conservativa), oppure time-exit a max_hold.
Una posizione per volta, equity sequenziale, netto spread, split train/test.
Stampa una GRIGLIA TP x SL con win-rate vero, aspettativa, PF, DD su TRAIN e TEST.

Uso: python3 tp_sl_grid.py <ohlc_h1.csv> [--win=250] [--lo=20] [--hi=80]
        [--max-hold=72] [--spread-pip=1.5] [--tps=10,15,20,30] [--sls=40,60,100,150]
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
    ap.add_argument("--max-hold", type=int, default=72)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    ap.add_argument("--tps", default="10,15,20,30")
    ap.add_argument("--sls", default="40,60,100,150")
    return ap.parse_args()

def rolling_pct_signed(x, W):
    out = np.full(len(x), np.nan)
    need = max(20, W // 4)
    for i in range(len(x)):
        lo = max(0, i - W + 1)
        w = x[lo:i+1]
        if i + 1 - lo >= need:
            out[i] = 100.0 * (w <= x[i]).mean()
    return out

def backtest(close, high, low, osc, lo, hi, tp, sl, max_hold, cost, pip, split):
    n = len(close)
    tp_d = tp * pip; sl_d = sl * pip
    i = 0
    res = {"tr": [], "te": []}
    while i < n:
        o = osc[i]
        if np.isnan(o):
            i += 1; continue
        d = 0
        if o < lo: d = +1
        elif o > hi: d = -1
        if d == 0:
            i += 1; continue
        entry = close[i]
        tp_px = entry + d*tp_d
        sl_px = entry - d*sl_d
        exit_pnl = None; j = i
        for k in range(i+1, min(i+1+max_hold, n)):
            j = k
            if d == +1:
                hit_sl = low[k] <= sl_px
                hit_tp = high[k] >= tp_px
            else:
                hit_sl = high[k] >= sl_px
                hit_tp = low[k] <= tp_px
            if hit_sl:                      # conservativo: SL prima del TP nello stesso bar
                exit_pnl = -sl - cost; break
            if hit_tp:
                exit_pnl = tp - cost; break
        if exit_pnl is None:                # time-exit a max_hold
            exit_pnl = (close[j]-entry)/pip*d - cost
        bucket = "tr" if j < split else "te"
        res[bucket].append(exit_pnl)
        i = j + 1                            # una posizione per volta
    return res

def summ(p):
    if not p: return None
    p = np.array(p)
    wins = p[p>0]; losses = p[p<0]
    pf = wins.sum()/-losses.sum() if losses.sum()!=0 else float('inf')
    eq = np.cumsum(p); dd = (eq-np.maximum.accumulate(eq)).min()
    return dict(N=len(p), tot=p.sum(), hit=(p>0).mean(), pf=pf, ev=p.mean(),
                dd=dd, retdd=(p.sum()/-dd if dd<0 else float('inf')))

def main():
    a = parse_args()
    TPS = [float(x) for x in a.tps.split(",")]
    SLS = [float(x) for x in a.sls.split(",")]
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    close = df["close"]; mas = np.column_stack([close.rolling(p).mean() for p in PERIODS])
    median = np.median(mas, axis=1)
    c = close.to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
    dMed = (c - median)/median*100.0
    osc = rolling_pct_signed(dMed, a.win)
    n = len(df); split = int(n*a.train_pct)

    print(f"\n=== TP/SL GRID | {a.csv.split('/')[-1]} | entrata distanza prezzo-mediana ===")
    print(f"win={a.win} lo={a.lo} hi={a.hi} maxHold={a.max_hold} spread={a.spread_pip}pip "
          f"barre={n}  (break-even hit = SL/(SL+TP))")
    for tp in TPS:
        print(f"\n  TP={tp:g}pip:")
        print(f"    {'SL':>5s} {'bkEv%':>6s} | {'TRAIN hit/PF/EV/Ret_DD':>30s} | {'TEST hit/PF/EV/Ret_DD':>30s}")
        for sl in SLS:
            r = backtest(c, high, low, osc, a.lo, a.hi, tp, sl, a.max_hold, a.spread_pip, pip, split)
            tr = summ(r["tr"]); te = summ(r["te"])
            be = sl/(sl+tp)*100
            def f(s):
                if not s: return f"{'-':>30s}"
                return f"N{s['N']:4d} {s['hit']*100:3.0f}%/{s['pf']:.2f}/{s['ev']:+5.1f}/{s['retdd']:+5.2f}"
            print(f"    {sl:>5g} {be:5.0f}% | {f(tr):>30s} | {f(te):>30s}")
    print("\n  Edge vero = TEST con PF>1 ED EV>0 ED hit > break-even, coerente col TRAIN.\n")

if __name__ == "__main__":
    main()
