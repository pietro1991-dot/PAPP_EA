#!/usr/bin/env python3
"""
gbpchf_validate.py - Valida la config del Motore Reversione (identica a EURGBP) su GBPCHF H6.
Replica la logica dell'EA: osc=percentile di (close-MA28)/MA28*100 su PctWindow=280 barre H6;
osc<10 BUY, >90 SELL; esci a osc=50 o dopo MaxHold=48 barre. Trade non sovrapposti, costo reale.
Split train(<2020)/test. Testo anche uno STOP rigido (per il rischio-coda CHF) per vederne il costo.
NESSUNA ri-taratura: stessi parametri di EURGBP (anti-overfit).
"""
import numpy as np, pandas as pd, sys
F="/home/pietro_giacobazzi/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/PAPP_Export.csv"
MAW=28; WIN=280; LO=10; HI=90; EXIT=50; MAXH=48; PIP=0.0001; SPLIT=pd.Timestamp("2020-01-01")
d=pd.read_csv(F); d["dt"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
c=d["close"].to_numpy(); hi=d["high"].to_numpy(); lo=d["low"].to_numpy(); dt=d["dt"].to_numpy()
n=len(c)
ma=pd.Series(c).rolling(MAW).mean().to_numpy()
dist=(c-ma)/ma*100.0
def rollpct(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        w=x[max(0,i-W+1):i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=100*(w<=x[i]).mean()
    return out
osc=rollpct(dist,WIN)
def backtest(cost,slpip):
    trades=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        dr=+1 if osc[i]<LO else (-1 if osc[i]>HI else 0)
        if dr==0: i+=1; continue
        entry=c[i]; j=i; stopped=False
        stop = (entry-slpip*PIP) if dr>0 else (entry+slpip*PIP)
        for k in range(i+1,min(i+1+MAXH,n)):
            j=k
            if slpip>0:
                if dr>0 and lo[k]<=stop: trades.append((dt[k],(stop-entry)/PIP-cost)); stopped=True; break
                if dr<0 and hi[k]>=stop: trades.append((dt[k],(entry-stop)/PIP-cost)); stopped=True; break
            if np.isnan(osc[k]): continue
            if (dr>0 and osc[k]>=EXIT) or (dr<0 and osc[k]<=EXIT): break
        if not stopped: trades.append((dt[j],(c[j]-entry)/PIP*dr-cost))
        i=j+1
    return trades
def rep(ts):
    if len(ts)<10: return f"N={len(ts)} (pochi)"
    p=np.array([t[1] for t in ts]); pos=p[p>0]; neg=p[p<0]
    pf=pos.sum()/-neg.sum() if neg.sum()!=0 else 9.99
    sd=p.std(ddof=1); t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
    eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
    return f"N={len(p):4d} EV={p.mean():+5.1f} tot={p.sum():+7.0f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f} DD={dd:+6.0f} R/DD={p.sum()/-dd if dd<0 else 9.9:.1f}"
print(f"=== GBPCHF H6 | config EURGBP identica (MA{MAW} WIN{WIN} {LO}/{HI} maxhold{MAXH}) | barre={n} ===\n")
for cost in (2.0,3.0):
    ts=backtest(cost,0)
    tr=[t for t in ts if t[0]<SPLIT]; te=[t for t in ts if t[0]>=SPLIT]
    print(f"  costo {cost}pip, NO stop:")
    print(f"    TRAIN {rep(tr)}")
    print(f"    TEST  {rep(te)}")
print("\n  --- effetto dello STOP rigido (costo 2pip) per il rischio-coda CHF ---")
for sl in (0,600,400,250):
    ts=backtest(2.0,sl)
    tr=[t for t in ts if t[0]<SPLIT]; te=[t for t in ts if t[0]>=SPLIT]
    a=np.array([t[1] for t in ts])
    print(f"    SL={sl:4d}pip: TUTTO tot={a.sum():+7.0f} | TRAIN {rep(tr)} | TEST {rep(te)}")
