#!/usr/bin/env python3
"""
backtest_reversion.py - Backtest TRADABILE della reversione (stile EA_RelVal) su H1.
osc = percentile rolling della distanza prezzo-linea (finestra W).
Entry: osc<Lo -> BUY ; osc>Hi -> SELL. Una posizione per volta.
Exit:  osc torna a ExitLevel (ritorno alla media) | MaxHold | (opz.) stop.
Costo round-trip in punti. Metriche: net, N, win%, PF, maxDD, per TRAIN/TEST (split 2020).

Uso: python3 backtest_reversion.py [../data/scalp_EURUSD_h1.csv] [--cost=12] [--split=2020.01.01]
"""
import sys, numpy as np
from numpy.lib.stride_tricks import sliding_window_view

PATH = "../data/scalp_EURUSD_h1.csv"
COST = 12.0
SPLIT = "2020.01.01"
PT = 0.00001
for a in sys.argv[1:]:
    if a.startswith("--cost="): COST = float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT = a.split("=")[1]
    elif not a.startswith("--"): PATH = a

# --- load ---
hdr = open(PATH, encoding="utf-8").readline().strip().split(",")
ix = {h: i for i, h in enumerate(hdr)}
raw = np.genfromtxt(PATH, delimiter=",", skip_header=1,
                    usecols=[ix["close"], ix["dMed"], ix["d30"], ix["d121"], ix["d182"], ix["d365"]],
                    dtype=float)
years = np.genfromtxt(PATH, delimiter=",", skip_header=1, usecols=[0], dtype="U4").astype(int)
close = raw[:, 0]
DIST = {"dMed": raw[:, 1], "d30": raw[:, 2], "d121": raw[:, 3], "d182": raw[:, 4], "d365": raw[:, 5]}
n = len(close)
split_i = int(np.argmax(years >= int(SPLIT[:4]))) if (years >= int(SPLIT[:4])).any() else n
print(f"File: {PATH} | barre H1: {n} | TRAIN<{SPLIT[:4]} ({split_i}) TEST ({n-split_i}) | costo {COST}pt\n")

def osc_series(d, W):
    o = np.full(n, np.nan)
    win = sliding_window_view(d, W)                 # (n-W+1, W) view
    center = d[W-1:]
    o[W-1:] = (win <= center[:, None]).mean(axis=1) * 100.0
    return o

def backtest(osc, Lo, Hi, ExitLevel, MaxHold, SL):
    pos = 0; entry = 0.0; ej = 0; dirn = 0
    tr = []   # (entry_index, pnl_points)
    for j in range(n):
        oj = osc[j]
        if oj != oj:  # nan
            continue
        if pos == 0:
            if oj < Lo:   pos, dirn, entry, ej = 1,  1, close[j], j
            elif oj > Hi: pos, dirn, entry, ej = 1, -1, close[j], j
        else:
            move = dirn*(close[j]-entry)/PT
            ex = ((dirn == 1 and oj >= ExitLevel) or (dirn == -1 and oj <= ExitLevel)
                  or (j-ej) >= MaxHold or (SL is not None and move < -SL))
            if ex:
                tr.append((ej, move - COST)); pos = 0
    return tr

def metrics(tr, lo, hi):
    p = [x[1] for x in tr if lo <= x[0] < hi]
    if not p: return None
    p = np.array(p)
    wins = p[p > 0]; loss = p[p < 0]
    pf = wins.sum()/abs(loss.sum()) if loss.sum() != 0 else float("inf")
    eq = np.cumsum(p); dd = float((np.maximum.accumulate(eq)-eq).max())
    return dict(N=len(p), net=float(p.sum()), avg=float(p.mean()),
                win=100*len(wins)/len(p), pf=pf, dd=dd)

# --- griglia ---
LINES = ["d30", "dMed", "d121"]
WS = [300, 500, 800]
THR = [(10, 90), (5, 95)]
HOLDS = [48, 96, 168]     # H1: 2, 4, 7 giorni
results = []
osccache = {}
for ln in LINES:
    for W in WS:
        key = (ln, W)
        osc = osccache.get(key) or osc_series(DIST[ln], W)
        osccache[key] = osc
        for (Lo, Hi) in THR:
            for MH in HOLDS:
                tr = backtest(osc, Lo, Hi, 50, MH, None)
                mtr = metrics(tr, 0, split_i); mte = metrics(tr, split_i, n)
                if not mtr or not mte: continue
                results.append((ln, W, Lo, Hi, MH, mtr, mte))

# --- leaderboard: robusti (train E test net>0), ordinati per net test ---
robust = [r for r in results if r[5]["net"] > 0 and r[6]["net"] > 0]
robust.sort(key=lambda r: r[6]["net"], reverse=True)
print(f"CONFIG ROBUSTE (net>0 in train E test): {len(robust)} su {len(results)}\n")
print(f"{'linea':5} {'W':>4} {'Lo/Hi':>6} {'MH':>4} | {'Ntr':>4} {'netTr':>7} {'PFtr':>4} {'DDtr':>6} | {'Nte':>4} {'netTe':>7} {'PFte':>4} {'DDte':>6} {'win%':>4}")
print("-"*96)
for ln, W, Lo, Hi, MH, a, b in robust[:12]:
    print(f"{ln:5} {W:>4} {Lo:>2}/{Hi:<3} {MH:>4} | {a['N']:>4} {a['net']:>7.0f} {a['pf']:>4.2f} {a['dd']:>6.0f} | "
          f"{b['N']:>4} {b['net']:>7.0f} {b['pf']:>4.2f} {b['dd']:>6.0f} {b['win']:>4.0f}")

if robust:
    ln, W, Lo, Hi, MH, a, b = robust[0]
    print(f"\n=== MIGLIORE: {ln} W={W} Lo/Hi={Lo}/{Hi} MaxHold={MH} — per anno (net punti) ===")
    osc = osccache[(ln, W)]
    tr = backtest(osc, Lo, Hi, 50, MH, None)
    from collections import defaultdict
    yr = defaultdict(lambda: [0.0, 0])
    for ej, pnl in tr:
        yr[years[ej]][0] += pnl; yr[years[ej]][1] += 1
    for y in sorted(yr):
        s, c = yr[y]
        print(f"  {y}: {s:>8.0f} pt  ({c} trade){'   <-- TEST' if y >= int(SPLIT[:4]) else ''}")
else:
    print("\nNessuna config robusta: la reversione non e' tradabile cosi'.")
