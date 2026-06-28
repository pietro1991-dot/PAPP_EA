#!/usr/bin/env python3
"""
vol_regime_ohlc.py - 'vol alta + struttura tesa -> reversione' su QUALSIASI OHLC.

Self-contained: legge OHLC (qualunque TF), ricampiona a D1, calcola 7 MA (periodi
in barre D1: 365..3), mediana, velocita' (pendenza mediana K=5), volatilita'
realizzata + percentile. Testa FADE/FOLLOW della velocita' sugli eventi ad alta
vol, trade NON sovrapposti, costo, split train/test.

Per testare un nuovo simbolo: esporta il suo OHLC (datetime,open,high,low,close)
e lancia. datetime in formato MT5 'YYYY.MM.DD HH:MM'.

Uso: python3 vol_regime_ohlc.py <ohlc.csv...> --mode=fade --volthr=0.7 --velmin=0.6 --hold=10
"""
import argparse
import numpy as np
import pandas as pd

PERIODS=[365,182,121,30,14,7,3]

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--mode", choices=["follow","fade"], default="fade")
    ap.add_argument("--volthr", type=float, default=0.70)
    ap.add_argument("--velmin", type=float, default=0.60)
    ap.add_argument("--hold", type=int, default=10)
    ap.add_argument("--volwin", type=int, default=20)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def rollpct(vals, use_abs, Wp=252):
    x=np.abs(vals) if use_abs else vals.astype(float); out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-Wp+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=(w<=x[i]).mean()
    return out

def run(path, a):
    df=pd.read_csv(path); df["datetime"]=pd.to_datetime(df["datetime"],format="%Y.%m.%d %H:%M")
    df=df.sort_values("datetime").set_index("datetime")
    d1=df.resample("1D").agg(open=("open","first"),high=("high","max"),
                             low=("low","min"),close=("close","last")).dropna()
    c=d1["close"].to_numpy(); n=len(d1); pip=0.0001
    if n<600: return None
    mas=np.column_stack([d1["close"].rolling(p).mean() for p in PERIODS])
    med=np.median(mas,axis=1)
    K=5; vraw=np.full(n,np.nan); vraw[K:]=(med[K:]-med[:-K])/med[:-K]*100.0
    sgnV=np.sign(vraw); velP=rollpct(vraw,True)
    logc=np.log(c); r=np.empty(n); r[0]=0; r[1:]=logc[1:]-logc[:-1]
    rv=pd.Series(r).rolling(a.volwin,min_periods=a.volwin//2).std().to_numpy()
    volP=rollpct(rv,False)
    split=int(n*a.train_pct); cost=a.spread_pip; sign=+1 if a.mode=="follow" else -1
    trades=[]; i=0
    while i<n-a.hold:
        if (not np.isnan(volP[i]) and volP[i]>a.volthr and sgnV[i]!=0
            and not np.isnan(velP[i]) and velP[i]>a.velmin):
            d=int(sign*sgnV[i]); j=i+a.hold
            trades.append((j,(c[j]-c[i])/pip*d-cost)); i=j
        else: i+=1
    def rep(ts):
        if len(ts)<10: return f"N={len(ts)} (pochi)"
        p=np.array([t[1] for t in ts]); w=p[p>0]; l=p[p<0]
        pf=w.sum()/-l.sum() if l.sum()!=0 else 9.99
        sd=p.std(ddof=1) if len(p)>1 else 0; t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
        return f"N={len(p):4d} EV={p.mean():+5.1f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f}"
    return rep([t for t in trades if t[0]<split]), rep([t for t in trades if t[0]>=split]), n

def main():
    a=parse_args()
    print(f"\n=== {a.mode.upper()} velocita' su eventi alta-vol | OHLC->D1 | volthr={a.volthr} "
          f"velmin={a.velmin} hold={a.hold} spread={a.spread_pip} ===")
    for path in a.csvs:
        res=run(path,a)
        nm=path.split("/")[-1]
        if res is None: print(f"  {nm:26s} (dati insufficienti)"); continue
        tr,te,n=res
        print(f"  {nm:26s} D1={n}  TRAIN[{tr}]  TEST[{te}]")
    print("  Edge = EV>0 PF>1 stesso segno TRAIN+TEST su TUTTI i simboli.\n")

if __name__=="__main__":
    main()
