#!/usr/bin/env python3
"""
relval_trendleg.py - Il modulo TREND per gli anni come il 2016 (EURGBP H6).
Idea: la reversione guadagna nei range; per i TREND serve un modulo separato che
segue il trend SOLO quando e' confermato (Efficiency Ratio alto). Qui isolo SOLO
la gamba trend e guardo il P&L anno per anno (specie 2016): se e' positiva nei trend
senza affossare gli altri anni, combinata con la reversione copre anche il 2016.
Entry: ER>erHigh -> segui (px>MA long, px<MA short). Exit: ER<erExit o cross MA o maxhold.
Uso: python3 relval_trendleg.py [--erhigh=0.5] [--erexit=0.3] [--ern=20] [--cost=1.5]
"""
import argparse, numpy as np, pandas as pd
BASE="../"
ap=argparse.ArgumentParser()
ap.add_argument("--erhigh",type=float,default=0.5); ap.add_argument("--erexit",type=float,default=0.3)
ap.add_argument("--ern",type=int,default=20); ap.add_argument("--ma",type=int,default=28)
ap.add_argument("--hold",type=int,default=120); ap.add_argument("--cost",type=float,default=1.5)
a=ap.parse_args(); pip=0.0001
def L(p,nm):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":nm}).set_index("datetime")
df=L(BASE+"EURUSD/OHLC_EURUSD_H1.csv","EUR").join(L(BASE+"GBPUSD/OHLC_GBPUSD_H1.csv","GBP"),how="inner").dropna().sort_index()
df=df.resample("6h").agg(EUR=("EUR","last"),GBP=("GBP","last")).dropna()
px=(df["EUR"]/df["GBP"]).to_numpy(); dates=df.index; n=len(px)
ma=pd.Series(px).rolling(a.ma).mean().to_numpy()
ch=np.abs(np.diff(px,prepend=px[0]))
er=np.full(n,np.nan)
for i in range(a.ern,n):
    den=ch[i-a.ern+1:i+1].sum(); er[i]=abs(px[i]-px[i-a.ern])/den if den>0 else 0.0
trades=[]; td=[]; i=a.ern+a.ma
while i<n-1:
    if np.isnan(er[i]) or np.isnan(ma[i]) or er[i]<a.erhigh: i+=1; continue
    d=+1 if px[i]>ma[i] else -1                 # segui il trend
    entry=px[i]; j=i
    for k in range(i+1,min(i+1+a.hold,n)):
        j=k
        if np.isnan(er[k]): continue
        cross = (d>0 and px[k]<ma[k]) or (d<0 and px[k]>ma[k])
        if er[k]<a.erexit or cross: break
    trades.append((px[j]-entry)/pip*d - a.cost); td.append(dates[i]); i=j+1
p=np.array(trades); s=pd.Series(p,index=pd.to_datetime(td)); yr=s.groupby(s.index.year).sum()
eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
pf=p[p>0].sum()/-p[p<0].sum() if p[p<0].sum()!=0 else 9.9
print(f"\n=== GAMBA TREND (solo ER>{a.erhigh}) EURGBP H6 | ma={a.ma} ern={a.ern} cost={a.cost} ===")
print(f"  tot={p.sum():+.0f}pip PF={pf:.2f} R/DD={p.sum()/-dd if dd<0 else 9.9:.1f} N={len(p)} anni+={int((yr>0).sum())}/{len(yr)}")
print(f"  anni: "+" ".join(f"{y}:{int(v):+d}" for y,v in yr.items()))
print()
