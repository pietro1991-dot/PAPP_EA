#!/usr/bin/env python3
"""
relval_compound.py - Il lotto che cresce col conto e' un vantaggio o un problema,
ORA che SAR ha ridotto il drawdown? Simula l'equity in DENARO della strategia
SAR (EURGBP H6) a lotto COSTANTE vs COMPOUNDING (lotto = equity/10000 * Pct/100),
e confronta capitale finale e max drawdown %.
Uso: python3 relval_compound.py [--pct=100] [--sar=80] [--init=10000]
"""
import argparse
import numpy as np
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--pct",type=float,default=100.0)
ap.add_argument("--sar",type=float,default=80.0)
ap.add_argument("--init",type=float,default=10000.0)
ap.add_argument("--cost",type=float,default=1.5)
ap.add_argument("--mawin",type=int,default=28)
ap.add_argument("--hold",type=int,default=48)
ap.add_argument("--lo",type=float,default=20.0)
ap.add_argument("--pipval",type=float,default=11.5)  # EUR per pip per 1.0 lotto EURGBP (approx)
a=ap.parse_args()
WIN=252; HI=100-a.lo; pip=0.0001; BASE="../"

def L(p,nm):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":nm}).set_index("datetime")
df=L(BASE+"EURUSD/OHLC_EURUSD_H1.csv","EUR").join(L(BASE+"GBPUSD/OHLC_GBPUSD_H1.csv","GBP"),how="inner").dropna().sort_index()
df=df.resample("6h").agg(EUR=("EUR","last"),GBP=("GBP","last")).dropna()
px=(df["EUR"]/df["GBP"]).to_numpy(); dates=df.index
ma=pd.Series(px).rolling(a.mawin).mean().to_numpy()
osc=np.full(len(px),np.nan)
for i in range(len(px)):
    lo=max(0,i-WIN+1); w=(px[lo:i+1]-ma[lo:i+1])/ma[lo:i+1]*100.0; w=w[~np.isnan(w)]
    if len(w)>=30:
        cur=(px[i]-ma[i])/ma[i]*100.0
        osc[i]=100*(w<=cur).mean()

# genera i trade SAR in ordine cronologico -> lista di (pips netti)
n=len(px); trades=[]; i=0
while i<n-1:
    if np.isnan(osc[i]): i+=1; continue
    d=+1 if osc[i]<a.lo else (-1 if osc[i]>HI else 0)
    if d==0: i+=1; continue
    entry=px[i]; pos=d; rev=False; j=i
    for k in range(i+1,min(i+1+a.hold,n)):
        j=k; move=(px[k]-entry)/pip*pos
        if (not rev) and a.sar>0 and move<=-a.sar:
            trades.append(-a.sar-a.cost); pos=-pos; entry=px[k]; rev=True; continue
        if (pos>0 and osc[k]>=50) or (pos<0 and osc[k]<=50): break
    trades.append((px[j]-entry)/pip*pos - a.cost); i=j+1

trades=np.array(trades)

def sim(compound):
    eq=a.init; peak=eq; maxdd=0.0; lot_fixed=(a.init/10000.0)*(a.pct/100.0)
    curve=[eq]
    for pips in trades:
        lot = (eq/10000.0)*(a.pct/100.0) if compound else lot_fixed
        if lot<0.01: lot=0.0
        eq += pips * a.pipval * lot
        if eq<=0: eq=0.0; curve.append(eq); break
        peak=max(peak,eq); dd=(peak-eq)/peak*100.0; maxdd=max(maxdd,dd)
        curve.append(eq)
    return eq, maxdd

print(f"\n=== COMPOUNDING vs COSTANTE | EURGBP H6 SAR={a.sar} | Pct={a.pct} init={a.init:.0f} | {len(trades)} trade ===")
for comp,lab in [(False,"COSTANTE   "),(True,"COMPOUNDING")]:
    fin,dd=sim(comp)
    ret=(fin/a.init-1)*100
    print(f"  {lab}: equity finale={fin:11.0f}  rendimento={ret:+8.0f}%  maxDD={dd:5.1f}%")
print()
