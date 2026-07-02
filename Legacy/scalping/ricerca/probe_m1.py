#!/usr/bin/env python3
"""
probe_m1.py - SONDA: il cross del prezzo (M5) sulle linee D1 predice un movimento
OLTRE IL COSTO? Segnale puro (esente da uscita): per ogni cross misura E[return
futuro a h barre NELLA direzione del cross], con t-stat, netto del costo, e
SEPARATAMENTE su TRAIN e TEST (un segnale conta solo se regge in entrambi).

⚠️ ~16 mesi di dati: meglio di niente, ma un solo regime lungo. Indicativo.

Uso: python3 probe_m1.py [../data/scalp_EURUSD_M5.csv] [--cost=12] [--split=2026.01.01]
"""
import sys, math

PATH = "../data/scalp_EURUSD_M5.csv"
COST = 12.0                 # costo round-trip in PUNTI (spread EURUSD ~1.2 pip)
SPLIT = "2026.01.01"        # <split = TRAIN, >=split = TEST
HORIZONS = [3, 6, 12, 24]   # barre M5 avanti = 15min, 30min, 1h, 2h
LINES = ["median", "MA365", "MA182", "MA121", "MA30", "MA14", "MA7", "MA3"]

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
CL = idx["close"]; ADX = idx["adx"]

def fnum(s):
    try: return float(s)
    except: return None

close = [fnum(r[CL]) for r in rows]
adx   = [fnum(r[ADX]) for r in rows]
dt    = [r[0] for r in rows]
PT = 0.00001
split_i = next((j for j in range(n) if dt[j] >= SPLIT), n)

print(f"File: {PATH} | barre: {n} | costo: {COST} pt | orizzonti M5: {HORIZONS}")
print(f"TRAIN < {SPLIT} ({split_i} barre) | TEST >= {SPLIT} ({n-split_i} barre)\n")

def stats(vals):
    if len(vals) < 2: return (vals[0] if vals else 0.0), 0.0
    m = sum(vals)/len(vals)
    sd = math.sqrt(sum((x-m)**2 for x in vals)/(len(vals)-1))
    t = m/(sd/math.sqrt(len(vals))) if sd > 0 else 0.0
    return m, t

def fwd(j, h, d):
    if j+h >= n: return None
    a, b = close[j], close[j+h]
    if a is None or b is None: return None
    return d*(b-a)/PT

print(f"{'linea':7} {'h':>3} | {'N_tr':>5} {'net_tr':>7} {'t_tr':>5} | {'N_te':>5} {'net_te':>7} {'t_te':>5} | verdetto")
print("-"*78)
for ln in LINES:
    xcol = idx["x"+("Med" if ln == "median" else ln.replace("MA", ""))]
    for h in HORIZONS:
        tr, te = [], []
        for j in range(n-h-1):
            xv = rows[j][xcol]
            d = 1 if xv == "1" else (-1 if xv == "-1" else 0)
            if d == 0: continue
            r = fwd(j, h, d)
            if r is None: continue
            (tr if j < split_i else te).append(r)
        if len(tr) < 20 or len(te) < 20: continue
        mtr, ttr = stats(tr); mte, tte = stats(te)
        ntr, nte = mtr-COST, mte-COST
        v = ""
        if ntr > 0 and nte > 0 and abs(ttr) > 2 and abs(tte) > 2: v = "★★ regge OOS"
        elif ntr > 0 and nte > 0: v = "★ entrambi >0 (debole)"
        elif (mtr > 0) != (mte > 0): v = "segno cambia (rumore)"
        print(f"{ln:7} {h:>3} | {len(tr):>5} {ntr:>7.1f} {ttr:>5.1f} | {len(te):>5} {nte:>7.1f} {tte:>5.1f} | {v}")

# --- ADX: separa continuazione da inversione? (MA30, h=6 = 30min) ---
print(f"\n--- ADX come filtro (MA30, h=6 barre = 30min) [in-sample, tutto] ---")
xcol = idx["x30"]
for label, lo, hi in [("ADX <20 (range)", 0, 20), ("ADX 20-25", 20, 25), ("ADX >25 (trend)", 25, 999)]:
    rr = []
    for j in range(n-7):
        xv = rows[j][xcol]
        d = 1 if xv == "1" else (-1 if xv == "-1" else 0)
        if d == 0: continue
        av = adx[j]
        if av is None or not (lo <= av < hi): continue
        r = fwd(j, 6, d)
        if r is not None: rr.append(r)
    if len(rr) < 20: print(f"  {label:16} N={len(rr)} (pochi)"); continue
    m, t = stats(rr)
    print(f"  {label:16} N={len(rr):>5}  lordo={m:>7.1f}  netto={m-COST:>7.1f}  t={t:>5.1f}")

print("\nLegenda: 'net' = punti medi per trade DOPO il costo. '★★' = candidato da validare con piu' storia.")
