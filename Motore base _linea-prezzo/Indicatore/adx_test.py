#!/usr/bin/env python3
"""
adx_test.py - L'ADX classico (Wilder) da' forza+direzione tradabile?

Calcola ADX/+DI/-DI sull'OHLC D1 (dagli export, che hanno O/H/L/C).
Entrata TREND-FOLLOW: ADX>thr e +DI>-DI -> long; -DI>+DI -> short.
Entrata REVERSIONE: stessa condizione, direzione opposta.
Trade NON sovrapposti, hold fisso, costo, split train/test, cross-strumento.

Uso: python3 adx_test.py <export.csv...> --period=14 --adxthr=25 --hold=10 --mode=follow|fade
"""
import argparse
import numpy as np
import pandas as pd

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--period", type=int, default=14)
    ap.add_argument("--adxthr", type=float, default=25)
    ap.add_argument("--hold", type=int, default=10)
    ap.add_argument("--mode", choices=["follow","fade"], default="follow")
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def wilder(s, p):
    return s.ewm(alpha=1.0/p, adjust=False).mean()

def adx(df, p):
    h=df["high"]; l=df["low"]; c=df["close"]
    pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    up=h.diff(); dn=-l.diff()
    plus_dm =np.where((up>dn)&(up>0), up, 0.0)
    minus_dm=np.where((dn>up)&(dn>0), dn, 0.0)
    atr=wilder(tr,p)
    pdi=100*wilder(pd.Series(plus_dm,index=df.index),p)/atr
    mdi=100*wilder(pd.Series(minus_dm,index=df.index),p)/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    adxl=wilder(dx.fillna(0),p)
    return adxl.to_numpy(), pdi.to_numpy(), mdi.to_numpy()

def run(path,a):
    df=pd.read_csv(path); df["datetime"]=pd.to_datetime(df["datetime"],format="%Y.%m.%d %H:%M")
    df=df.sort_values("datetime").reset_index(drop=True)
    pip=0.0001; c=df["close"].to_numpy(); n=len(df)
    A,P,M=adx(df,a.period)
    split=int(n*a.train_pct); cost=a.spread_pip; sign=+1 if a.mode=="follow" else -1
    trades=[]; i=a.period*3
    while i<n-a.hold:
        if not np.isnan(A[i]) and A[i]>a.adxthr and P[i]!=M[i]:
            base_dir = +1 if P[i]>M[i] else -1
            d=sign*base_dir; j=i+a.hold
            trades.append((j,(c[j]-c[i])/pip*d-cost)); i=j
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
    print(f"\n=== ADX {a.mode.upper()} | period={a.period} adxthr={a.adxthr} hold={a.hold} spread={a.spread_pip} ===")
    for path in a.csvs:
        tr,te=run(path,a)
        print(f"  {path.split('/')[-1]:28s} TRAIN[{tr}]  TEST[{te}]")
    print("  Edge = EV>0 PF>1 stesso segno TRAIN+TEST su TUTTI gli strumenti.\n")

if __name__=="__main__":
    main()
