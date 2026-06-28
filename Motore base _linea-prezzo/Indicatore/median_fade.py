#!/usr/bin/env python3
"""
median_fade.py - Backtest dell'idea: fade della distanza prezzo-mediana.

Oscillatore = percentile (0..100) della distanza con segno close-mediana (dMed%)
su finestra trailing W. Entra LONG quando osc < soglia_bassa (prezzo molto sotto
la mediana), SHORT quando osc > soglia_alta. Esce al ritorno verso 50 (reversione
completata) o dopo max_hold barre. Una posizione per volta, equity sequenziale,
netto spread. Split temporale train/test.

Uso: python3 median_fade.py <csv> [--win=100] [--lo=20] [--hi=80]
                            [--exit=50] [--max-hold=20] [--spread-pip=1.5]
"""
import sys, argparse
import numpy as np
import pandas as pd

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--win", type=int, default=100)
    ap.add_argument("--lo", type=float, default=20)
    ap.add_argument("--hi", type=float, default=80)
    ap.add_argument("--exit", type=float, default=50)
    ap.add_argument("--max-hold", type=int, default=20)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    ap.add_argument("--stop-pip", type=float, default=0.0, help="0 = nessuno stop")
    return ap.parse_args()

def rolling_pct_signed(x, W):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        lo = max(0, i - W + 1)
        w = x[lo:i+1]; w = w[~np.isnan(w)]
        if len(w) >= max(20, W//4):
            out[i] = 100.0 * (w <= x[i]).mean()
    return out

def backtest(close, osc, lo, hi, exitlvl, max_hold, cost_pip, stop_pip, pip):
    n = len(close)
    pos = 0        # +1 long, -1 short, 0 flat
    entry_px = 0.0; entry_i = 0
    trades = []    # (exit_index, pnl_pip)
    for i in range(n):
        o = osc[i]
        if np.isnan(o):
            continue
        if pos == 0:
            if o < lo: pos, entry_px, entry_i = +1, close[i], i
            elif o > hi: pos, entry_px, entry_i = -1, close[i], i
        else:
            held = i - entry_i
            move = (close[i] - entry_px) / pip * pos    # pip a favore
            hit_exit = (pos == +1 and o >= exitlvl) or (pos == -1 and o <= exitlvl)
            hit_stop = (stop_pip > 0 and move <= -stop_pip)
            hit_time = held >= max_hold
            if hit_exit or hit_stop or hit_time:
                trades.append((i, move - cost_pip))
                pos = 0
    return trades

def summ(trades):
    if not trades:
        return None
    p = np.array([t[1] for t in trades])
    wins = p[p > 0]; losses = p[p < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() != 0 else float('inf')
    sd = p.std(ddof=1) if len(p) > 1 else 0.0
    t = p.mean() / (sd/np.sqrt(len(p))) if sd > 0 else 0.0
    # max drawdown su equity cumulata
    eq = np.cumsum(p); peak = np.maximum.accumulate(eq); dd = (eq - peak).min()
    return dict(N=len(p), tot=p.sum(), mean=p.mean(), hit=(p>0).mean(),
                pf=pf, t=t, dd=dd)

def main():
    a = parse_args()
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    close = df["close"].to_numpy()
    dMed = df["dMed%"].to_numpy()
    osc = rolling_pct_signed(dMed, a.win)

    n = len(df); split = int(n * a.train_pct)
    trades = backtest(close, osc, a.lo, a.hi, a.exit, a.max_hold,
                      a.spread_pip, a.stop_pip, pip)
    tr = [t for t in trades if t[0] < split]
    te = [t for t in trades if t[0] >= split]

    print(f"\n=== MEDIAN FADE | {a.csv.split('/')[-1]} ===")
    print(f"win={a.win} lo={a.lo} hi={a.hi} exit={a.exit} maxHold={a.max_hold} "
          f"stop={a.stop_pip} spread={a.spread_pip}pip  barre={n}")
    for label, s in [("TRAIN", summ(tr)), ("TEST", summ(te)), ("TUTTO", summ(trades))]:
        if not s:
            print(f"  {label:6s}: nessun trade"); continue
        print(f"  {label:6s}: N={s['N']:4d}  tot={s['tot']:+8.0f}pip  "
              f"media={s['mean']:+5.1f}  hit={s['hit']*100:4.0f}%  "
              f"PF={s['pf']:4.2f}  t={s['t']:+5.2f}  maxDD={s['dd']:+7.0f}pip")
    print()

if __name__ == "__main__":
    main()
