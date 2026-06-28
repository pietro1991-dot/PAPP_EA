#!/usr/bin/env python3
"""
classifier.py - Classificatore RIMBALZO vs SFONDAMENTO sugli estremi dell'oscillatore.

Evento = osc distanza prezzo-mediana < lo (BUY) o > hi (SELL), trade NON sovrapposti.
Esito = exit quando osc torna a 50 (la strategia di reversione). label=1 se vince.
Feature SOLO al momento dell'entrata (no look-ahead): estensione, velocita'/accel
struttura, volatilita' realizzata, momentum, ATR, posizione nel range, frattale
fast-slow, ora/giorno, persistenza estremo.

Onesta':
 - split TEMPORALE 70/30 (no shuffle)
 - soglia di selezione scelta sul TRAIN, applicata al TEST
 - metrica = EV di trading OOS (pip netto spread) sui trade selezionati, non accuratezza
 - confronto vs baseline "tradare tutto" e vs AUC

Uso: python3 classifier.py <ohlc_h1.csv> [--win=250] [--lo=20] [--hi=80]
        [--spread-pip=1.0] [--max-hold=500]
"""
import argparse
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

PERIODS = [365, 182, 121, 30, 14, 7, 3]

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--win", type=int, default=250)
    ap.add_argument("--lo", type=float, default=20)
    ap.add_argument("--hi", type=float, default=80)
    ap.add_argument("--spread-pip", type=float, default=1.0)
    ap.add_argument("--max-hold", type=int, default=500)
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
    c = df["close"].to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
    mas = np.column_stack([df["close"].rolling(p).mean() for p in PERIODS])
    median = np.median(mas, axis=1)
    osc = rolling_pct_signed((c-median)/median*100.0, a.win)
    n = len(df)
    hour = df["datetime"].dt.hour.to_numpy(); dow = df["datetime"].dt.dayofweek.to_numpy()

    logc = np.log(c); ret = np.empty(n); ret[0]=0; ret[1:] = logc[1:]-logc[:-1]
    def roll(arr, w, fn):
        s = pd.Series(arr); return getattr(s.rolling(w, min_periods=max(5,w//3)), fn)().to_numpy()
    rv24 = roll(ret,24,'std'); rv120 = roll(ret,120,'std')
    atr24 = roll(high-low,24,'mean')/pip
    hi120 = roll(high,120,'max'); lo120 = roll(low,120,'min')
    fast = np.nanmean(mas[:, 4:7], axis=1); slow = np.nanmean(mas[:, 0:3], axis=1)
    frattale = (fast - slow)/median*1e4
    K=5
    vel = np.full(n,np.nan); vel[K:] = (median[K:]-median[:-K])/median[:-K]*1e4
    acc = np.full(n,np.nan); acc[1:] = vel[1:]-vel[:-1]

    # genera trade NON sovrapposti + feature all'entrata + esito
    rows = []
    i = 0
    while i < n:
        o = osc[i]
        if np.isnan(o): i+=1; continue
        d = +1 if o < a.lo else (-1 if o > a.hi else 0)
        if d==0: i+=1; continue
        # esito: exit a osc=50
        entry=c[i]; j=i
        for k in range(i+1, min(i+1+a.max_hold,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d==+1 and osc[k]>=50) or (d==-1 and osc[k]<=50): break
        gross=(c[j]-entry)/pip*d
        # feature (note: orientate col segno del trade dove utile)
        denomr = (hi120[i]-lo120[i])
        rangepos = (c[i]-lo120[i])/denomr if denomr>0 else 0.5
        feat = {
            "ext": abs((c[i]-median[i])/median[i]*100.0),
            "osc_dist": abs(o-50),
            "vel_align": (vel[i]*d) if not np.isnan(vel[i]) else 0.0,   # >0 = struttura va come il trade (contro reversione)
            "acc_align": (acc[i]*d) if not np.isnan(acc[i]) else 0.0,
            "rv24": rv24[i]*1e4 if not np.isnan(rv24[i]) else 0.0,
            "rv120": rv120[i]*1e4 if not np.isnan(rv120[i]) else 0.0,
            "rv_ratio": (rv24[i]/rv120[i]) if (rv120[i] and not np.isnan(rv24[i]) and not np.isnan(rv120[i]) and rv120[i]>0) else 1.0,
            "atr24": atr24[i] if not np.isnan(atr24[i]) else 0.0,
            "mom24": (c[i]-c[max(0,i-24)])/pip*d,                       # momentum nel verso del trade
            "rangepos_signed": (rangepos-0.5)*d,
            "frattale_align": (frattale[i]*d) if not np.isnan(frattale[i]) else 0.0,
            "hour": hour[i], "dow": dow[i],
        }
        rows.append((i, j, d, gross, feat))
        i = j+1

    idxs = np.array([r[0] for r in rows])
    pnl  = np.array([r[3] for r in rows])
    y    = (pnl > 0).astype(int)
    feats = pd.DataFrame([r[4] for r in rows])
    split = int(n*a.train_pct)
    tr = idxs < split; te = ~tr
    Xtr, Xte = feats[tr].to_numpy(), feats[te].to_numpy()
    ytr, yte = y[tr], y[te]
    pnl_tr, pnl_te = pnl[tr], pnl[te]
    cost = a.spread_pip

    print(f"\n=== CLASSIFICATORE rimbalzo vs sfondamento | {a.csv.split('/')[-1]} ===")
    print(f"eventi: train={tr.sum()} (win {ytr.mean()*100:.0f}%)  test={te.sum()} (win {yte.mean()*100:.0f}%)")
    print(f"BASELINE 'tradare tutto'  -> EV test = {(pnl_te-cost).mean():+.2f} pip/trade  "
          f"(tot {(pnl_te-cost).sum():+.0f})")

    clf = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05,
                                         l2_regularization=1.0, random_state=0)
    clf.fit(Xtr, ytr)
    ptr = clf.predict_proba(Xtr)[:,1]; pte = clf.predict_proba(Xte)[:,1]
    auc_tr = roc_auc_score(ytr, ptr); auc_te = roc_auc_score(yte, pte)
    print(f"AUC  train={auc_tr:.3f}  test={auc_te:.3f}   (0.5=inutile; gap grande=overfit)")

    # soglia: scegli sul TRAIN quella che massimizza EV train, applicala al TEST
    best_thr, best_ev = 0.5, -1e9
    for thr in np.quantile(ptr, np.linspace(0.0,0.9,19)):
        sel = ptr >= thr
        if sel.sum() < 50: continue
        ev = (pnl_tr[sel]-cost).mean()
        if ev > best_ev: best_ev, best_thr = ev, thr
    sel_te = pte >= best_thr
    print(f"\nsoglia P>={best_thr:.3f} (scelta su train, EV train {best_ev:+.2f})")
    if sel_te.sum() > 0:
        ev_te = (pnl_te[sel_te]-cost)
        wins = ev_te[ev_te>0]; losses = ev_te[ev_te<0]
        pf = wins.sum()/-losses.sum() if losses.sum()!=0 else float('inf')
        print(f"  TEST selezionati: N={sel_te.sum()}/{te.sum()}  win={yte[sel_te].mean()*100:.0f}%  "
              f"EV={ev_te.mean():+.2f} pip/trade  tot={ev_te.sum():+.0f}  PF={pf:.2f}")
    else:
        print("  nessun trade selezionato sul test")

    # curva: EV test per decile di probabilita'
    print("\n  EV test per decile di P(rimbalzo) [dal piu' improbabile al piu' probabile]:")
    q = np.quantile(pte, np.linspace(0,1,11))
    for b in range(10):
        m = (pte>=q[b]) & (pte<=q[b+1]) if b==9 else (pte>=q[b]) & (pte<q[b+1])
        if m.sum()>0:
            print(f"    D{b+1}: N={m.sum():4d}  win={yte[m].mean()*100:3.0f}%  EV={ (pnl_te[m]-cost).mean():+5.1f}")

    from sklearn.inspection import permutation_importance
    pi = permutation_importance(clf, Xte, yte, n_repeats=5, random_state=0, scoring="roc_auc")
    imp = sorted(zip(feats.columns, pi.importances_mean), key=lambda x:-x[1])
    print("\n  Importanza feature (permutazione su TEST, ~0 = inutile):",
          ", ".join(f"{k}={v:+.3f}" for k,v in imp[:8]))
    print()

if __name__ == "__main__":
    main()
