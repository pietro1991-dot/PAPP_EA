#!/usr/bin/env python3
"""
probe_shortlines.py - LINEE CORTE NATIVE su M5 (non le D1-anchored): MA veloci
calcolate sulle barre M5, e i loro incroci. Domande:
 A) il prezzo che incrocia una MA veloce M5 predice qualcosa (follow o fade)?
 B) l'incrocio linea-linea (MAfast x MAslow, il classico golden/death cross) funziona?
Netto del costo, TRAIN/TEST. Segnale puro a orizzonte fisso.

Uso: python3 probe_shortlines.py [../data/scalp_EURUSD_M5.csv] [--cost=12] [--split=2026.01.01]
"""
import sys, numpy as np

PATH = "../data/scalp_EURUSD_M5.csv"
COST = 12.0
SPLIT = "2026.01.01"
PT = 0.00001
for a in sys.argv[1:]:
    if a.startswith("--cost="): COST = float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT = a.split("=")[1]
    elif not a.startswith("--"): PATH = a

hdr = open(PATH, encoding="utf-8").readline().strip().split(",")
ix = {h: i for i, h in enumerate(hdr)}
close = np.genfromtxt(PATH, delimiter=",", skip_header=1, usecols=[ix["close"]], dtype=float)
yrs = np.genfromtxt(PATH, delimiter=",", skip_header=1, usecols=[0], dtype="U4").astype(int)
n = len(close)
split_i = int(np.argmax(yrs >= int(SPLIT[:4]))) if (yrs >= int(SPLIT[:4])).any() else n
HZ = [3, 6, 12]   # M5: 15min, 30min, 1h

def sma(x, p):
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.full(len(x), np.nan)
    out[p-1:] = (c[p:] - c[:-p]) / p
    return out

def stats(v):
    if len(v) < 2: return 0.0, 0.0
    m = v.mean(); sd = v.std(ddof=1)
    return m, (m/(sd/np.sqrt(len(v))) if sd > 0 else 0.0)

def evalsig(entry_idx, dirs):
    """entry_idx: array indici; dirs: +1/-1. Ritorna per ogni h: (Ntr,netTr,tTr,Nte,netTe,tTe)."""
    out = {}
    for h in HZ:
        rtr, rte = [], []
        for j, d in zip(entry_idx, dirs):
            if j+h >= n: continue
            r = d*(close[j+h]-close[j])/PT
            (rtr if j < split_i else rte).append(r)
        rtr = np.array(rtr); rte = np.array(rte)
        if len(rtr) < 20 or len(rte) < 20: out[h] = None; continue
        mtr, ttr = stats(rtr); mte, tte = stats(rte)
        out[h] = (len(rtr), mtr-COST, ttr, len(rte), mte-COST, tte)
    return out

def show(name, res):
    for h in HZ:
        r = res.get(h)
        if r is None: print(f"  {name:22} h={h:>2}  (pochi)"); continue
        Ntr, ntr, ttr, Nte, nte, tte = r
        v = "★★" if (ntr>0 and nte>0 and abs(ttr)>2 and abs(tte)>2) else ("★" if (ntr>0 and nte>0) else "")
        print(f"  {name:22} h={h:>2} | tr N={Ntr:>5} net={ntr:>6.1f} t={ttr:>5.1f} | te N={Nte:>5} net={nte:>6.1f} t={tte:>5.1f} {v}")

print(f"File: {PATH} | n={n} | costo={COST}pt | TRAIN<{SPLIT[:4]} ({split_i}) TEST ({n-split_i})")
print("MA native su barre M5 (non D1-anchored). '★★' = regge train+test.\n")

# --- A) prezzo incrocia una MA veloce M5 (follow e fade) ---
print("A) PREZZO x MA veloce M5")
for p in [5, 10, 20, 50]:
    ma = sma(close, p)
    up, dn = [], []
    for j in range(p, n-1):
        if np.isnan(ma[j]) or np.isnan(ma[j-1]): continue
        if close[j-1] < ma[j-1] and close[j] >= ma[j]: up.append(j)
        elif close[j-1] > ma[j-1] and close[j] <= ma[j]: dn.append(j)
    idx = np.array(up+dn); dfollow = np.array([1]*len(up)+[-1]*len(dn))
    show(f"px x MA{p} FOLLOW", evalsig(idx, dfollow))
    show(f"px x MA{p} FADE",   evalsig(idx, -dfollow))

# --- B) incrocio linea-linea M5 (golden/death cross) ---
print("\nB) INCROCIO MAfast x MAslow (golden/death cross), follow")
for pf, ps in [(5, 20), (10, 50), (20, 100)]:
    mf, ms = sma(close, pf), sma(close, ps)
    idx, dirs = [], []
    for j in range(ps, n-1):
        if np.isnan(mf[j]) or np.isnan(ms[j]) or np.isnan(mf[j-1]) or np.isnan(ms[j-1]): continue
        if mf[j-1] <= ms[j-1] and mf[j] > ms[j]: idx.append(j); dirs.append(1)   # golden
        elif mf[j-1] >= ms[j-1] and mf[j] < ms[j]: idx.append(j); dirs.append(-1) # death
    show(f"MA{pf}xMA{ps} follow", evalsig(np.array(idx), np.array(dirs)))
    show(f"MA{pf}xMA{ps} FADE",   evalsig(np.array(idx), -np.array(dirs)))

print("\nNota: gross = net + costo. Se il gross e' ~0 in ogni riga, non c'e' pattern (solo rumore + costo).")
