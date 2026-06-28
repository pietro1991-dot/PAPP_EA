#!/usr/bin/env python3
"""
relval.py - RELATIVE VALUE: i cross sintetici revertono (edge ortogonale)?

EUR/GBP/CHF condividono la gamba USD. Combinandoli il dollaro si cancella:
  EURGBP = EURUSD / GBPUSD
  EURCHF = EURUSD * USDCHF
  GBPCHF = GBPUSD * USDCHF
Resta il valore RELATIVO, che mean-reverte meglio del singolo. Testo la reversione
distanza-dalla-media sul cross: entro all'estremo (osc<lo/>hi), esco al centro,
trade NON sovrapposti, costo, split train/test. Confronto col singolo (breakeven).

Usa gli export D1 (allineati per data). Uso: python3 relval.py
"""
import argparse
import numpy as np
import pandas as pd

BASE="../"
PATHS={"EURUSD":BASE+"EURUSD/PAPP_Export.csv",
       "GBPUSD":BASE+"GBPUSD/PAPP_Export_GBPUSD.csv",
       "USDCHF":BASE+"USDCHF/PAPP_Export_USDCHF.csv"}
_ap=argparse.ArgumentParser()
_ap.add_argument("--cost",type=float,default=1.0)
_ap.add_argument("--mawin",type=int,default=30)
_ap.add_argument("--lo",type=float,default=20)
_a=_ap.parse_args()
WIN=252; LO=_a.lo; HI=100-_a.lo; HOLD_MAX=60; COST=_a.cost; TRAIN=0.70; MAWIN=_a.mawin

def load(p):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":p}).set_index("datetime")

def rollpct_signed(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-W+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=100*(w<=x[i]).mean()
    return out

def bt(price, name):
    n=len(price); c=price; pip=0.0001
    ma=pd.Series(c).rolling(MAWIN).mean().to_numpy()
    dist=(c-ma)/ma*100.0
    osc=rollpct_signed(dist,WIN)
    split=int(n*TRAIN); trades=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<LO else (-1 if osc[i]>HI else 0)
        if d==0: i+=1; continue
        entry=c[i]; j=i
        for k in range(i+1,min(i+1+HOLD_MAX,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d==+1 and osc[k]>=50) or (d==-1 and osc[k]<=50): break
        trades.append((j,(c[j]-entry)/pip*d-COST)); i=j+1
    def rep(ts):
        if len(ts)<10: return f"N={len(ts)}(pochi)"
        p=np.array([t[1] for t in ts]); w=p[p>0]; l=p[p<0]
        pf=w.sum()/-l.sum() if l.sum()!=0 else 9.99
        sd=p.std(ddof=1) if len(p)>1 else 0; t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
        eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
        rdd=p.sum()/-dd if dd<0 else 9.99
        return f"N={len(p):4d} EV={p.mean():+5.1f} tot={p.sum():+6.0f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f} DD={dd:+5.0f} R/DD={rdd:.1f}"
    tr=[t for t in trades if t[0]<split]; te=[t for t in trades if t[0]>=split]
    print(f"  {name:10s} TRAIN[{rep(tr)}]  TEST[{rep(te)}]")

def main():
    df=load(PATHS["EURUSD"]).join(load(PATHS["GBPUSD"]),how="inner").join(load(PATHS["USDCHF"]),how="inner").dropna()
    df=df.sort_index()
    eur=df[PATHS["EURUSD"]].to_numpy(); gbp=df[PATHS["GBPUSD"]].to_numpy(); chf=df[PATHS["USDCHF"]].to_numpy()
    print(f"\n=== RELATIVE VALUE (cross sintetici) | barre allineate={len(df)} | spread {COST}pip ===")
    print("  -- singoli (riferimento, breakeven atteso) --")
    bt(eur,"EURUSD"); bt(gbp,"GBPUSD"); bt(chf,"USDCHF")
    print("  -- CROSS (USD cancellato) --")
    bt(eur/gbp,"EURGBP"); bt(eur*chf,"EURCHF"); bt(gbp*chf,"GBPCHF")
    print("\n  Edge ortogonale = cross con EV>0 PF>1 su TRAIN e TEST, meglio dei singoli.\n")

if __name__=="__main__":
    main()
