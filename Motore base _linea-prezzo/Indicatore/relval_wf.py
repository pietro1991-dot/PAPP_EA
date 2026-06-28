#!/usr/bin/env python3
"""
relval_wf.py - Walk-forward severo del relative-value sui cross.
Parametri FISSI (no ottimizzazione per periodo). Per ogni cross stampa il P&L
ANNO PER ANNO e per 5 fold di calendario: un edge vero deve fare soldi nella
maggioranza dei periodi indipendenti, non solo in aggregato.
Uso: python3 relval_wf.py [--cost=2.5] [--mawin=30] [--lo=20]
"""
import argparse
import numpy as np
import pandas as pd

BASE="../"
P={"EURUSD":BASE+"EURUSD/PAPP_Export.csv","GBPUSD":BASE+"GBPUSD/PAPP_Export_GBPUSD.csv",
   "USDCHF":BASE+"USDCHF/PAPP_Export_USDCHF.csv"}
ap=argparse.ArgumentParser()
ap.add_argument("--cost",type=float,default=2.5); ap.add_argument("--mawin",type=int,default=30)
ap.add_argument("--lo",type=float,default=20); a=ap.parse_args()
WIN=252; HOLD_MAX=60

def load(p):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":p}).set_index("datetime")

def rollpct_signed(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-W+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=100*(w<=x[i]).mean()
    return out

def trades_of(price, dates):
    n=len(price); c=price; pip=0.0001
    ma=pd.Series(c).rolling(a.mawin).mean().to_numpy()
    osc=rollpct_signed((c-ma)/ma*100.0, WIN)
    res=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<a.lo else (-1 if osc[i]>(100-a.lo) else 0)
        if d==0: i+=1; continue
        entry=c[i]; j=i
        for k in range(i+1,min(i+1+HOLD_MAX,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d==+1 and osc[k]>=50) or (d==-1 and osc[k]<=50): break
        res.append((dates[i],(c[j]-entry)/pip*d-a.cost)); i=j+1
    return res

def main():
    df=load(P["EURUSD"]).join(load(P["GBPUSD"]),how="inner").join(load(P["USDCHF"]),how="inner").dropna().sort_index()
    dates=df.index.to_numpy()
    eur=df[P["EURUSD"]].to_numpy(); gbp=df[P["GBPUSD"]].to_numpy(); chf=df[P["USDCHF"]].to_numpy()
    crosses={"EURGBP":eur/gbp,"EURCHF":eur*chf,"GBPCHF":gbp*chf}
    print(f"\n=== WALK-FORWARD relative-value | cost={a.cost} ma={a.mawin} soglia={a.lo}/{100-a.lo} ===")
    for nm,px in crosses.items():
        tr=trades_of(px,dates)
        s=pd.Series([t[1] for t in tr], index=pd.to_datetime([t[0] for t in tr]))
        yearly=s.groupby(s.index.year).agg(['sum','count'])
        years=yearly.index.tolist()
        pos=int((yearly['sum']>0).sum()); tot=len(yearly)
        line=" ".join(f"{y}:{int(yearly.loc[y,'sum']):+d}" for y in years)
        # 5 fold uguali
        folds=np.array_split(np.arange(len(s)),5)
        fs=[]
        for f in folds:
            if len(f)==0: continue
            p=s.values[f]; fs.append(f"{p.sum():+.0f}({len(f)})")
        print(f"\n  {nm}: anni positivi {pos}/{tot} | tot {s.sum():+.0f}pip su {len(s)} trade")
        print(f"    per anno: {line}")
        print(f"    5 fold:   {'  '.join(fs)}")
    print()

if __name__=="__main__":
    main()
