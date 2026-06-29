#!/usr/bin/env python3
"""
relval_filter.py - Reversione EURGBP con FILTRO TREND: opera solo quando il mercato
OSCILLA, sta fermo quando TRENDA. Misura del regime = Efficiency Ratio di Kaufman:
  ER = |close[t]-close[t-N]| / somma|variazioni| ultime N barre.  ER alto = trend, basso = range.
Entra in reversione SOLO se ER < erThr (range). Confronta col plain (nessun filtro),
guarda se taglia gli anni-trend in perdita. Trade non sovrapposti, costo, anno per anno.
Uso: python3 relval_filter.py [--tf=D1] [--er=0.35] [--ern=20] [--cost=2.5]
"""
import argparse
import numpy as np
import pandas as pd
BASE="../"
ap=argparse.ArgumentParser()
ap.add_argument("--tf",default="D1"); ap.add_argument("--er",type=float,default=0.35)
ap.add_argument("--ern",type=int,default=20); ap.add_argument("--cost",type=float,default=2.5)
ap.add_argument("--mawin",type=int,default=30); ap.add_argument("--lo",type=float,default=20)
ap.add_argument("--hold",type=int,default=60); a=ap.parse_args()
WIN=252; HI=100-a.lo; pip=0.0001
_RULE={"H4":"4h","H6":"6h","H8":"8h"}
def L(p,nm):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":nm}).set_index("datetime")
if a.tf=="D1":
    df=L(BASE+"EURUSD/PAPP_Export.csv","EUR").join(L(BASE+"GBPUSD/PAPP_Export_GBPUSD.csv","GBP"),how="inner")
else:
    df=L(BASE+"EURUSD/OHLC_EURUSD_H1.csv","EUR").join(L(BASE+"GBPUSD/OHLC_GBPUSD_H1.csv","GBP"),how="inner")
df=df.dropna().sort_index()
if a.tf!="D1": df=df.resample(_RULE[a.tf]).agg(EUR=("EUR","last"),GBP=("GBP","last")).dropna()
px=(df["EUR"]/df["GBP"]).to_numpy(); dates=df.index; n=len(px)
ma=pd.Series(px).rolling(a.mawin).mean().to_numpy()
osc=np.full(n,np.nan)
dist=(px-ma)/ma*100.0
for i in range(n):
    lo=max(0,i-WIN+1); w=dist[lo:i+1]; w=w[~np.isnan(w)]
    if len(w)>=30: osc[i]=100*(w<=dist[i]).mean()
# Efficiency Ratio
ch=np.abs(np.diff(px,prepend=px[0]))
er=np.full(n,np.nan)
for i in range(a.ern,n):
    denom=ch[i-a.ern+1:i+1].sum()
    er[i]= abs(px[i]-px[i-a.ern])/denom if denom>0 else 0.0

def bt(use_filter):
    trades=[]; td=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<a.lo else (-1 if osc[i]>HI else 0)
        if d==0: i+=1; continue
        if use_filter and (np.isnan(er[i]) or er[i]>=a.er):   # trend in corso -> salta
            i+=1; continue
        entry=px[i]; j=i
        for k in range(i+1,min(i+1+a.hold,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d>0 and osc[k]>=50) or (d<0 and osc[k]<=50): break
        trades.append((px[j]-entry)/pip*d - a.cost); td.append(dates[i]); i=j+1
    return trades,td
def rep(lbl,tr,td):
    if len(tr)<5: print(f"  {lbl}: pochi"); return
    p=np.array(tr); eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
    pf=p[p>0].sum()/-p[p<0].sum() if p[p<0].sum()!=0 else 9.9
    s=pd.Series(p,index=pd.to_datetime(td)); yr=s.groupby(s.index.year).sum()
    print(f"  {lbl}: tot={p.sum():+.0f} PF={pf:.2f} R/DD={p.sum()/-dd if dd<0 else 9.9:.1f} N={len(p)} anni+={int((yr>0).sum())}/{len(yr)}")
    print(f"    anni: "+" ".join(f"{y}:{int(v):+d}" for y,v in yr.items()))
print(f"\n=== EURGBP reversione + FILTRO TREND (Efficiency Ratio) | TF={a.tf} erThr={a.er} erN={a.ern} cost={a.cost} ===")
tp,td=bt(False); rep("PLAIN ",tp,td)
tf_,tfd=bt(True); rep("FILTER",tf_,tfd)
print()
