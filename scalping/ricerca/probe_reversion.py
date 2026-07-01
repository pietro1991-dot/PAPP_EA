#!/usr/bin/env python3
"""
probe_reversion.py - Meccanismo REVERSIONE (come il Motore Reversione, ma su M5 vs
linee D1): quando il prezzo M5 e' TROPPO LONTANO da una linea D1 (overextension in
percentile estremo), poi RIENTRA verso la linea? Si FADE l'estremo.

Entry: quando |distanza dalla linea| ENTRA in un percentile estremo (fresh).
  prezzo molto SOPRA la linea -> SELL (bet: torna giu')
  prezzo molto SOTTO         -> BUY  (bet: torna su')
Return NELLA direzione del fade, a vari orizzonti, netto del costo, TRAIN/TEST.
Soglia percentile calcolata SUL TRAIN e applicata anche al TEST (niente look-ahead).

Uso: python3 probe_reversion.py [../data/scalp_EURUSD_M5.csv] [--cost=12] [--split=2026.01.01] [--pct=90]
"""
import sys, math

PATH = "../data/scalp_EURUSD_M5.csv"
COST = 12.0
SPLIT = "2026.01.01"
PCT = 90.0                      # percentile estremo di |distanza| per entrare
HORIZONS = [6, 12, 24, 48]      # M5: 30min, 1h, 2h, 4h (la reversione ha bisogno di tempo)
LINES = ["median", "MA30", "MA121", "MA182", "MA365"]   # livelli D1 strutturali

for a in sys.argv[1:]:
    if a.startswith("--cost="): COST = float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT = a.split("=")[1]
    elif a.startswith("--pct="): PCT = float(a.split("=")[1])
    elif not a.startswith("--"): PATH = a

rows = []
with open(PATH, encoding="utf-8") as f:
    head = f.readline().strip().split(",")
    idx = {name: i for i, name in enumerate(head)}
    for line in f:
        rows.append(line.rstrip("\n").split(","))
n = len(rows)
CL = idx["close"]

def fnum(s):
    try: return float(s)
    except: return None

close = [fnum(r[CL]) for r in rows]
dt    = [r[0] for r in rows]
PT = 0.00001
split_i = next((j for j in range(n) if dt[j] >= SPLIT), n)
DCOL = {"median": "dMed", "MA30": "d30", "MA121": "d121", "MA182": "d182", "MA365": "d365"}

def pctl(vals, p):
    s = sorted(vals); k = int(p/100.0*(len(s)-1))
    return s[k]

def stats(vals):
    if len(vals) < 2: return (vals[0] if vals else 0.0), 0.0
    m = sum(vals)/len(vals)
    sd = math.sqrt(sum((x-m)**2 for x in vals)/(len(vals)-1))
    return m, (m/(sd/math.sqrt(len(vals))) if sd > 0 else 0.0)

def fwd_fade(j, h, dist):
    """return NELLA direzione del fade (contro il segno della distanza), in punti."""
    if j+h >= n: return None
    a, b = close[j], close[j+h]
    if a is None or b is None: return None
    fade_dir = -1 if dist > 0 else 1
    return fade_dir*(b-a)/PT

print(f"File: {PATH} | n={n} | costo={COST}pt | percentile estremo={PCT} | orizzonti M5={HORIZONS}")
print(f"TRAIN<{SPLIT} ({split_i}) | TEST>={SPLIT} ({n-split_i})\n")
print(f"{'linea':7} {'h':>3} | {'N_tr':>5} {'net_tr':>7} {'t_tr':>5} | {'N_te':>5} {'net_te':>7} {'t_te':>5} | verdetto")
print("-"*78)

for ln in LINES:
    dc = idx[DCOL[ln]]
    dist = [fnum(r[dc]) for r in rows]
    # soglia |dist| dal TRAIN
    absd_tr = [abs(x) for x in dist[:split_i] if x is not None]
    if len(absd_tr) < 100: continue
    thr = pctl(absd_tr, PCT)
    for h in HORIZONS:
        tr, te = [], []
        prev_extreme = False
        for j in range(n-h-1):
            d = dist[j]
            if d is None: prev_extreme = False; continue
            extreme = abs(d) >= thr
            fresh = extreme and not prev_extreme    # entra solo all'INGRESSO nell'estremo
            prev_extreme = extreme
            if not fresh: continue
            r = fwd_fade(j, h, d)
            if r is None: continue
            (tr if j < split_i else te).append(r)
        if len(tr) < 15 or len(te) < 15: continue
        mtr, ttr = stats(tr); mte, tte = stats(te)
        ntr, nte = mtr-COST, mte-COST
        v = ""
        if ntr > 0 and nte > 0 and abs(ttr) > 2 and abs(tte) > 2: v = "★★ regge OOS"
        elif ntr > 0 and nte > 0: v = "★ entrambi >0"
        elif (mtr > 0) != (mte > 0): v = "segno cambia (rumore)"
        print(f"{ln:7} {h:>3} | {len(tr):>5} {ntr:>7.1f} {ttr:>5.1f} | {len(te):>5} {nte:>7.1f} {tte:>5.1f} | {v}  (thr={thr:.0f}pt)")

print("\nNota: '★★' = fade dell'overextension che regge train+test. Gross = net+costo.")
