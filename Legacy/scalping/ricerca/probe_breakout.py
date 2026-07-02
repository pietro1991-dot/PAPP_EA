#!/usr/bin/env python3
"""
probe_breakout.py - FIGURA: SQUEEZE -> BREAKOUT su M5.
La rottura da' la direzione (non il cross). Domande:
 (1) una rottura del range (max/min ultime K barre) continua, oltre il costo?
 (2) NULL DECISIVO: le rotture DOPO una compressione (ATR basso) battono
     le rotture NORMALI? (se no, lo "squeeze" non aggiunge nulla)
Return nella direzione della rottura, netto costo, TRAIN/TEST.

Uso: python3 probe_breakout.py [../data/scalp_EURUSD_M5.csv] [--cost=12] [--split=2026.01.01]
"""
import sys, math

PATH = "../data/scalp_EURUSD_M5.csv"
COST = 12.0
SPLIT = "2026.01.01"
KS = [12, 24]                 # range di rottura: ultime 12 (1h) / 24 (2h) barre M5
HORIZONS = [6, 12, 24]        # 30min, 1h, 2h
SQ_PCT = 30.0                 # "squeeze" = ATR sotto il 30° percentile (train)

for a in sys.argv[1:]:
    if a.startswith("--cost="): COST = float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT = a.split("=")[1]
    elif not a.startswith("--"): PATH = a

rows = []
with open(PATH, encoding="utf-8") as f:
    head = f.readline().strip().split(",")
    idx = {name: i for i, name in enumerate(head)}
    for line in f:
        rows.append(line.rstrip("\n").split(","))
n = len(rows)

def fnum(s):
    try:
        v = float(s); return v if math.isfinite(v) else None
    except: return None

close = [fnum(r[idx["close"]]) for r in rows]
high  = [fnum(r[idx["high"]])  for r in rows]
low   = [fnum(r[idx["low"]])   for r in rows]
atr   = [fnum(r[idx["atr"]])   for r in rows]
dt    = [r[0] for r in rows]
PT = 0.00001
split_i = next((j for j in range(n) if dt[j] >= SPLIT), n)

def pctl(vals, p):
    s = sorted(vals); return s[int(p/100.0*(len(s)-1))]
def stats(vals):
    if len(vals) < 2: return (vals[0] if vals else 0.0), 0.0
    m = sum(vals)/len(vals)
    sd = math.sqrt(sum((x-m)**2 for x in vals)/(len(vals)-1))
    return m, (m/(sd/math.sqrt(len(vals))) if sd > 0 else 0.0)
def fwd(j, h, d):
    if j+h >= n: return None
    a, b = close[j], close[j+h]
    if a is None or b is None: return None
    return d*(b-a)/PT

atr_tr = [x for x in atr[:split_i] if x is not None]
sq_thr = pctl(atr_tr, SQ_PCT)
print(f"File: {PATH} | n={n} | costo={COST}pt | squeeze=ATR<{sq_thr:.0f}pt (p{SQ_PCT:.0f} train)")
print(f"TRAIN<{SPLIT} ({split_i}) | TEST>={SPLIT} ({n-split_i})\n")
print(f"{'K':>3} {'h':>3} {'set':>8} | {'N_tr':>6} {'net_tr':>7} {'t_tr':>5} | {'N_te':>6} {'net_te':>7} {'t_te':>5} | verdetto")
print("-"*82)

for K in KS:
    for h in HORIZONS:
        allb = {"tr": [], "te": []}
        sqb  = {"tr": [], "te": []}
        for j in range(K, n-h-1):
            c = close[j]
            if c is None: continue
            hh = [high[k] for k in range(j-K, j) if high[k] is not None]
            ll = [low[k]  for k in range(j-K, j) if low[k]  is not None]
            if len(hh) < K or len(ll) < K: continue
            up = c > max(hh); dn = c < min(ll)
            if not (up or dn): continue
            d = 1 if up else -1
            r = fwd(j, h, d)
            if r is None: continue
            seg = "tr" if j < split_i else "te"
            allb[seg].append(r)
            av = atr[j]
            if av is not None and av <= sq_thr:
                sqb[seg].append(r)
        for name, dd in [("TUTTE", allb), ("SQUEEZE", sqb)]:
            if len(dd["tr"]) < 20 or len(dd["te"]) < 20:
                print(f"{K:>3} {h:>3} {name:>8} | (pochi eventi)"); continue
            mtr, ttr = stats(dd["tr"]); mte, tte = stats(dd["te"])
            ntr, nte = mtr-COST, mte-COST
            v = ""
            if ntr > 0 and nte > 0 and abs(ttr) > 2 and abs(tte) > 2: v = "★★ regge OOS"
            elif ntr > 0 and nte > 0: v = "★ entrambi >0"
            elif (mtr > 0) != (mte > 0): v = "segno cambia"
            print(f"{K:>3} {h:>3} {name:>8} | {len(dd['tr']):>6} {ntr:>7.1f} {ttr:>5.1f} | {len(dd['te']):>6} {nte:>7.1f} {tte:>5.1f} | {v}")
    print()

print("NULL DECISIVO: se 'SQUEEZE' non batte 'TUTTE', la compressione non aggiunge nulla.")
