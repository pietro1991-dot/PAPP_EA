#!/usr/bin/env python3
"""
relval_h1.py - Relative-value reversione su EURGBP a scala ORARIA (piu' veloce).
EURGBP = EURUSD_H1 / GBPUSD_H1 (USD cancellato). Oscillatore = percentile (finestra W)
della distanza close-MA(mawin). Entra <lo/>hi, esce al centro, NON sovrapposti, costo,
split train/test + P&L anno per anno. Parametri in BARRE H1.
Uso: python3 relval_h1.py --mawin=24 --win=480 --lo=20 --hold=72 --cost=1.5
"""
import argparse
import numpy as np
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--mawin",type=int,default=24); ap.add_argument("--win",type=int,default=480)
ap.add_argument("--lo",type=float,default=20); ap.add_argument("--hold",type=int,default=72)
ap.add_argument("--cost",type=float,default=1.5)
ap.add_argument("--tf",default="H1")   # H1, H4, H6, H8, D1
a=ap.parse_args()
HI=100-a.lo
_RULE={"H1":None,"H2":"2h","H4":"4h","H6":"6h","H8":"8h","D1":"1D"}

def load(p,nm):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":nm}).set_index("datetime")

def rollpct(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-W+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=W//4: out[i]=100*(w<=x[i]).mean()
    return out

def main():
    eu=load("../EURUSD/OHLC_EURUSD_H1.csv","EUR")
    gb=load("../GBPUSD/OHLC_GBPUSD_H1.csv","GBP")
    df=eu.join(gb,how="inner").dropna().sort_index()
    rule=_RULE.get(a.tf)
    if rule is not None:
        df=df.resample(rule).agg(EUR=("EUR","last"),GBP=("GBP","last")).dropna()
    px=(df["EUR"]/df["GBP"]).to_numpy(); dates=df.index
    n=len(px); pip=0.0001
    ma=pd.Series(px).rolling(a.mawin).mean().to_numpy()
    osc=rollpct((px-ma)/ma*100.0, a.win)
    trades=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<a.lo else (-1 if osc[i]>HI else 0)
        if d==0: i+=1; continue
        entry=px[i]; j=i
        for k in range(i+1,min(i+1+a.hold,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d==+1 and osc[k]>=50) or (d==-1 and osc[k]<=50): break
        trades.append((dates[i],(px[j]-entry)/pip*d-a.cost)); i=j+1
    s=pd.Series([t[1] for t in trades], index=pd.to_datetime([t[0] for t in trades]))
    split=int(len(s)*0.70)
    def rep(p):
        if len(p)<10: return "pochi"
        p=np.array(p); w=p[p>0]; l=p[p<0]; pf=w.sum()/-l.sum() if l.sum()!=0 else 9.99
        sd=p.std(ddof=1) if len(p)>1 else 0; t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
        eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min(); rdd=p.sum()/-dd if dd<0 else 9.99
        return f"N={len(p):4d} EV={p.mean():+5.2f} tot={p.sum():+6.0f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f} R/DD={rdd:.1f}"
    print(f"\n=== EURGBP H1 relval | ma={a.mawin} win={a.win} soglia={a.lo}/{HI} hold={a.hold} cost={a.cost} | barre={n} ===")
    print(f"  TRAIN {rep(s.values[:split])}")
    print(f"  TEST  {rep(s.values[split:])}")
    yearly=s.groupby(s.index.year).sum()
    pos=int((yearly>0).sum())
    print(f"  anni positivi {pos}/{len(yearly)}: "+" ".join(f"{y}:{int(v):+d}" for y,v in yearly.items()))
    print(f"  trade/anno medio ~ {len(s)/max(1,len(yearly)):.0f}\n")

if __name__=="__main__":
    main()
