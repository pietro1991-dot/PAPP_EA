#!/usr/bin/env python3
"""
feat_adx_test.py - Frattale e Accelerazione come segnali forza+direzione (ADX nostro).

Frattale = squadra veloce(MA3+7+14) - lenta(MA121+182+365) [colonna 'spread'].
  direzione = segno; forza = percentile di |frattale|.
Accel = derivata 2a della mediana (robusta, dal 'median'); segno+percentile.

Segnali (trade NON sovrapposti, hold fisso, costo, split train/test, cross-strumento):
  frat_follow / frat_fade : forza>thr, direzione = segno frattale (o opposto)
  frat_cross              : il frattale cambia segno (veloce incrocia lento) -> entra nel nuovo segno
  accel_follow / accel_fade

Uso: python3 feat_adx_test.py <export.csv...> --signal=frat_follow --thr=0.6 --hold=10
"""
import argparse
import numpy as np
import pandas as pd

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--signal", required=True,
                    choices=["frat_follow","frat_fade","frat_cross","accel_follow","accel_fade"])
    ap.add_argument("--thr", type=float, default=0.60)
    ap.add_argument("--hold", type=int, default=10)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def rollpct(vals, Wp=252):
    x=np.abs(vals); out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-Wp+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=(w<=x[i]).mean()
    return out

def run(path,a):
    df=pd.read_csv(path); df["datetime"]=pd.to_datetime(df["datetime"],format="%Y.%m.%d %H:%M")
    df=df.sort_values("datetime").reset_index(drop=True)
    pip=0.0001; c=df["close"].to_numpy(); n=len(df)
    frat=df["spread"].to_numpy()                      # frattale = fastAvg-slowAvg
    fratP=rollpct(frat); sgnF=np.sign(frat)
    sgnF_prev=np.concatenate([[0],sgnF[:-1]])
    med=df["median"].to_numpy(); K=5
    araw=np.full(n,np.nan); araw[2*K:]=(med[2*K:]-2.0*med[K:-K]+med[:-2*K])
    accP=rollpct(araw); sgnA=np.sign(araw)
    split=int(n*a.train_pct); cost=a.spread_pip

    def entry(i):
        s=a.signal
        if s=="frat_follow":  return int(sgnF[i]) if (fratP[i]>a.thr) else 0
        if s=="frat_fade":    return int(-sgnF[i]) if (fratP[i]>a.thr) else 0
        if s=="frat_cross":   return int(sgnF[i]) if (sgnF[i]!=0 and sgnF[i]!=sgnF_prev[i] and sgnF_prev[i]!=0) else 0
        if s=="accel_follow": return int(sgnA[i]) if (accP[i]>a.thr) else 0
        if s=="accel_fade":   return int(-sgnA[i]) if (accP[i]>a.thr) else 0
        return 0

    trades=[]; i=2*K+1
    while i<n-a.hold:
        if np.isnan(fratP[i]) or np.isnan(accP[i]): i+=1; continue
        d=entry(i)
        if d!=0:
            j=i+a.hold; trades.append((j,(c[j]-c[i])/pip*d-cost)); i=j
        else: i+=1
    def rep(ts):
        if len(ts)<10: return f"N={len(ts)} (pochi)"
        p=np.array([t[1] for t in ts]); w=p[p>0]; l=p[p<0]
        pf=w.sum()/-l.sum() if l.sum()!=0 else 9.99
        sd=p.std(ddof=1) if len(p)>1 else 0; t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
        return f"N={len(p):4d} EV={p.mean():+5.1f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f}"
    return rep([t for t in trades if t[0]<split]), rep([t for t in trades if t[0]>=split])

def main():
    a=parse_args()
    print(f"\n=== {a.signal} | thr={a.thr} hold={a.hold} spread={a.spread_pip} ===")
    for path in a.csvs:
        tr,te=run(path,a)
        print(f"  {path.split('/')[-1]:28s} TRAIN[{tr}]  TEST[{te}]")
    print("  Edge = EV>0 PF>1 stesso segno TRAIN+TEST su TUTTI gli strumenti.\n")

if __name__=="__main__":
    main()
