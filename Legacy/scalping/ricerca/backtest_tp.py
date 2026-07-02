#!/usr/bin/env python3
"""
backtest_tp.py - Variante: reversione con TP STRETTO + SL LARGO (profilo "97% win"
del Motore Base), SENZA uscita a osc=50. Entry uguale (osc<Lo BUY / osc>Hi SELL).
Uscita: TP colpito (win) | SL colpito (loss) | MaxHold. TP/SL intrabar su high/low.
Ipotesi CONSERVATIVA: se in una barra si toccano sia TP che SL, conta SL.
Confronto con la baseline (uscita a osc=50): TEST net ~+35.000pt, PF 1.31, win 58%.

Uso: python3 backtest_tp.py [../data/scalp_EURUSD_h1.csv] [--cost=12] [--split=2020.01.01]
"""
import sys, numpy as np
from numpy.lib.stride_tricks import sliding_window_view

PATH = "../data/scalp_EURUSD_h1.csv"
COST = 12.0
SPLIT = "2020.01.01"
PT = 0.00001
W = 300; LO = 5.0; HI = 95.0
for a in sys.argv[1:]:
    if a.startswith("--cost="): COST = float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT = a.split("=")[1]
    elif not a.startswith("--"): PATH = a

hdr = open(PATH, encoding="utf-8").readline().strip().split(",")
ix = {h: i for i, h in enumerate(hdr)}
d = np.genfromtxt(PATH, delimiter=",", skip_header=1,
                  usecols=[ix["close"], ix["high"], ix["low"], ix["dMed"]], dtype=float)
yrs = np.genfromtxt(PATH, delimiter=",", skip_header=1, usecols=[0], dtype="U4").astype(int)
close, high, low, dmed = d[:, 0], d[:, 1], d[:, 2], d[:, 3]
n = len(close)
split_i = int(np.argmax(yrs >= int(SPLIT[:4]))) if (yrs >= int(SPLIT[:4])).any() else n

# osc = percentile rolling di dMed
osc = np.full(n, np.nan)
win = sliding_window_view(dmed, W); center = dmed[W-1:]
osc[W-1:] = (win <= center[:, None]).mean(axis=1)*100.0

def backtest(TP, SL, MaxHold):
    j = W; tr = []
    while j < n-1:
        o = osc[j]
        if o != o: j += 1; continue
        if o < LO: dirn = 1
        elif o > HI: dirn = -1
        else: j += 1; continue
        entry = close[j]; ek = None; pnl = None
        end = min(j+MaxHold, n)
        for k in range(j+1, end):
            if dirn == 1:
                if low[k]  <= entry - SL*PT: pnl = -SL; ek = k; break
                if high[k] >= entry + TP*PT: pnl =  TP; ek = k; break
            else:
                if high[k] >= entry + SL*PT: pnl = -SL; ek = k; break
                if low[k]  <= entry - TP*PT: pnl =  TP; ek = k; break
        if pnl is None:
            ek = end-1; pnl = dirn*(close[ek]-entry)/PT
        tr.append((j, pnl - COST)); j = ek+1
    return tr

def metrics(tr, lo, hi):
    p = np.array([x[1] for x in tr if lo <= x[0] < hi])
    if len(p) < 10: return None
    w = p[p > 0]; l = p[p < 0]
    pf = w.sum()/abs(l.sum()) if l.sum() != 0 else float("inf")
    eq = np.cumsum(p); dd = float((np.maximum.accumulate(eq)-eq).max())
    return dict(N=len(p), net=float(p.sum()), win=100*len(w)/len(p), pf=pf, dd=dd)

print(f"File: {PATH} | n={n} | costo={COST}pt | W={W} {LO:.0f}/{HI:.0f} | TRAIN<{SPLIT[:4]} TEST\n")
print(f"{'TP':>4} {'SL':>4} {'MH':>4} | {'Ntr':>5} {'netTr':>7} {'PFtr':>4} {'winTr':>5} {'DDtr':>6} | {'Nte':>5} {'netTe':>7} {'PFte':>4} {'winTe':>5} {'DDte':>6}")
print("-"*92)
best = None
for TP in [40, 80, 120, 200]:
    for SL in [200, 400]:
        for MH in [48, 96]:
            tr = backtest(TP, SL, MH)
            a = metrics(tr, 0, split_i); b = metrics(tr, split_i, n)
            if not a or not b: continue
            flag = "  ★" if (a["net"] > 0 and b["net"] > 0) else ""
            print(f"{TP:>4} {SL:>4} {MH:>4} | {a['N']:>5} {a['net']:>7.0f} {a['pf']:>4.2f} {a['win']:>4.0f}% {a['dd']:>6.0f} | "
                  f"{b['N']:>5} {b['net']:>7.0f} {b['pf']:>4.2f} {b['win']:>4.0f}% {b['dd']:>6.0f}{flag}")
            if b["net"] > 0 and a["net"] > 0 and (best is None or b["net"] > best[1]):
                best = ((TP, SL, MH), b["net"])

print("\nBaseline (uscita a osc=50, no TP): TEST net ~+35.000pt · PF 1.31 · win 58%")
print("Se il TP stretto alza il win% ma abbassa net/PF -> conferma: taglia i vincenti (come EURGBP).")
