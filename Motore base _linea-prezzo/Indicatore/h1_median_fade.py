#!/usr/bin/env python3
"""
h1_median_fade.py - L'idea dell'utente sul TF CORRENTE (H1), non ancorata a D1.

7 MA calcolate sul TF corrente con periodi in BARRE (365/182/121/30/14/7/3 barre H1),
mediana delle 7, oscillatore = percentile con segno della distanza close-mediana
su finestra trailing W (barre H1). Fade: LONG sotto 'lo', SHORT sopra 'hi',
uscita al ritorno verso 50 o dopo max_hold; stop opzionale; 1 posizione/volta;
equity sequenziale; netto spread; split train/test.

Uso: python3 h1_median_fade.py <ohlc_h1.csv> [--win=250] [--lo=20] [--hi=80]
        [--exit=50] [--max-hold=48] [--stop-pip=30] [--spread-pip=1.5]
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
    ap.add_argument("--exit", type=float, default=50)
    ap.add_argument("--max-hold", type=int, default=48)
    ap.add_argument("--stop-pip", type=float, default=30)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
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

def backtest(close, osc, lo, hi, exitlvl, max_hold, cost, stop, pip):
    n = len(close); pos = 0; entry_px = 0.0; entry_i = 0; trades = []
    for i in range(n):
        o = osc[i]
        if np.isnan(o):
            continue
        if pos == 0:
            if o < lo: pos, entry_px, entry_i = +1, close[i], i
            elif o > hi: pos, entry_px, entry_i = -1, close[i], i
        else:
            move = (close[i] - entry_px) / pip * pos
            hit_exit = (pos == +1 and o >= exitlvl) or (pos == -1 and o <= exitlvl)
            hit_stop = (stop > 0 and move <= -stop)
            hit_time = (i - entry_i) >= max_hold
            if hit_exit or hit_stop or hit_time:
                trades.append((i, move - cost)); pos = 0
    return trades

def summ(trades):
    if not trades: return None
    p = np.array([t[1] for t in trades])
    losses = p[p < 0]; wins = p[p > 0]
    pf = wins.sum() / -losses.sum() if losses.sum() != 0 else float('inf')
    sd = p.std(ddof=1) if len(p) > 1 else 0.0
    t = p.mean()/(sd/np.sqrt(len(p))) if sd > 0 else 0.0
    eq = np.cumsum(p); dd = (eq - np.maximum.accumulate(eq)).min()
    return dict(N=len(p), tot=p.sum(), mean=p.mean(), hit=(p>0).mean(), pf=pf, t=t, dd=dd)

def main():
    a = parse_args()
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    close = df["close"]
    mas = np.column_stack([close.rolling(p).mean().to_numpy() for p in PERIODS])
    median = np.median(mas, axis=1)                  # mediana 7 MA (NaN finche' MA365 non pronta)
    c = close.to_numpy()
    dMed = (c - median) / median * 100.0
    osc = rolling_pct_signed(dMed, a.win)

    n = len(df); split = int(n * a.train_pct)
    tr = backtest(close=c, osc=osc, lo=a.lo, hi=a.hi, exitlvl=a.exit,
                  max_hold=a.max_hold, cost=a.spread_pip, stop=a.stop_pip, pip=pip)
    train = [t for t in tr if t[0] < split]
    test  = [t for t in tr if t[0] >= split]

    print(f"\n=== H1 MEDIAN FADE | {a.csv.split('/')[-1]} | periodi in barre H1 ===")
    print(f"win={a.win} lo={a.lo} hi={a.hi} exit={a.exit} maxHold={a.max_hold} "
          f"stop={a.stop_pip} spread={a.spread_pip}pip  barre={n}")
    for label, s in [("TRAIN", summ(train)), ("TEST", summ(test)), ("TUTTO", summ(tr))]:
        if not s: print(f"  {label:6s}: nessun trade"); continue
        print(f"  {label:6s}: N={s['N']:5d}  tot={s['tot']:+8.0f}pip  media={s['mean']:+5.1f}  "
              f"hit={s['hit']*100:4.0f}%  PF={s['pf']:4.2f}  t={s['t']:+5.2f}  maxDD={s['dd']:+7.0f}")
    print()

if __name__ == "__main__":
    main()
