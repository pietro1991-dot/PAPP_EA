#!/usr/bin/env python3
"""
hour_analysis.py - L'entrata distanza-mediana condizionata dall'ORA del giorno.

Ipotesi: la reversione (prezzo esteso vs mediana) non è uniforme nelle 24h;
nelle ore di bassa volatilità il rimbalzo è più affidabile (edge ortogonale alle
feature, che sono "senza tempo"). Per ogni ora server stampa N, hit-rate, EV e PF
di un trade reversione con TP/SL fisso (max/min reali), su TRAIN e TEST.

Uso: python3 hour_analysis.py <ohlc_h1.csv> [--lo=20] [--hi=80]
        [--tp=20] [--sl=60] [--max-hold=24] [--spread-pip=1.0] [--win=250]
"""
import argparse
import numpy as np
import pandas as pd

PERIODS = [365, 182, 121, 30, 14, 7, 3]

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--lo", type=float, default=20)
    ap.add_argument("--hi", type=float, default=80)
    ap.add_argument("--tp", type=float, default=20)
    ap.add_argument("--sl", type=float, default=60)
    ap.add_argument("--max-hold", type=int, default=24)
    ap.add_argument("--spread-pip", type=float, default=1.0)
    ap.add_argument("--win", type=int, default=250)
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def rolling_pct_signed(x, W):
    out = np.full(len(x), np.nan); need = max(20, W//4)
    for i in range(len(x)):
        lo = max(0, i-W+1); w = x[lo:i+1]
        if i+1-lo >= need: out[i] = 100.0*(w <= x[i]).mean()
    return out

def main():
    a = parse_args()
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    hour = df["datetime"].dt.hour.to_numpy()
    close = df["close"]; mas = np.column_stack([close.rolling(p).mean() for p in PERIODS])
    median = np.median(mas, axis=1)
    c = close.to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
    osc = rolling_pct_signed((c-median)/median*100.0, a.win)
    n = len(df); split = int(n*a.train_pct)
    tp_d = a.tp*pip; sl_d = a.sl*pip

    # trade reversione sequenziali; ogni trade etichettato con l'ora di ENTRATA
    rows = []  # (entry_hour, pnl, exit_idx)
    i = 0
    while i < n:
        o = osc[i]
        if np.isnan(o): i += 1; continue
        d = +1 if o < a.lo else (-1 if o > a.hi else 0)
        if d == 0: i += 1; continue
        entry = c[i]; tp_px = entry+d*tp_d; sl_px = entry-d*sl_d
        pnl = None; j = i
        for k in range(i+1, min(i+1+a.max_hold, n)):
            j = k
            hit_sl = (low[k] <= sl_px) if d>0 else (high[k] >= sl_px)
            hit_tp = (high[k] >= tp_px) if d>0 else (low[k] <= tp_px)
            if hit_sl: pnl = -a.sl - a.spread_pip; break
            if hit_tp: pnl =  a.tp - a.spread_pip; break
        if pnl is None: pnl = (c[j]-entry)/pip*d - a.spread_pip
        rows.append((hour[i], pnl, j)); i = j+1

    be = a.sl/(a.sl+a.tp)*100
    print(f"\n=== HIT-RATE PER ORA | {a.csv.split('/')[-1]} | entrata distanza-mediana ===")
    print(f"lo={a.lo} hi={a.hi} TP={a.tp} SL={a.sl} (break-even {be:.0f}%) "
          f"maxHold={a.max_hold} spread={a.spread_pip}pip")
    print(f"{'ora':>3s} | {'TRAIN  N/hit/EV/PF':>22s} | {'TEST  N/hit/EV/PF':>22s}")
    print("-"*56)
    def stat(p):
        if len(p) < 10: return None
        p = np.array(p); w=p[p>0]; l=p[p<0]
        pf = w.sum()/-l.sum() if l.sum()!=0 else float('inf')
        return f"N{len(p):3d} {(p>0).mean()*100:3.0f}% {p.mean():+5.1f} {pf:.2f}"
    best = []
    for h in range(24):
        tr = [r[1] for r in rows if r[0]==h and r[2]<split]
        te = [r[1] for r in rows if r[0]==h and r[2]>=split]
        st, se = stat(tr), stat(te)
        mark = ""
        if st and se:
            trp = np.array(tr); tep = np.array(te)
            if trp.mean()>0 and tep.mean()>0: mark = "  <== positivo train+test"; best.append(h)
        print(f"{h:3d} | {st or '-':>22s} | {se or '-':>22s}{mark}")
    print(f"\nOre positive su train E test (TP{a.tp:g}/SL{a.sl:g}): {best or 'nessuna'}\n")

if __name__ == "__main__":
    main()
