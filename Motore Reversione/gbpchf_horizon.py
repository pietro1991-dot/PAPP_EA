#!/usr/bin/env python3
"""
gbpchf_horizon.py - L'edge GBPCHF e' a orizzonte GIORNALIERO, non settimanale.
La config EURGBP-H6 (MA28 barre=7gg) e' morta su GBPCHF; il D1 (MA28=28gg) era fortissimo.
Testo su GBPCHF H6 REALE vari orizzonti scalati (4 barre H6/giorno), train/test, costo reale.
Se l'orizzonte ~28gg funziona anche sul prezzo REALE -> edge vero, params giornalieri.
Se non funziona -> il D1 sintetico era artefatto e GBPCHF si scarta.
"""
import numpy as np, pandas as pd
F="/home/pietro_giacobazzi/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files/PAPP_Export.csv"
LO=10; HI=90; EXIT=50; PIP=0.0001; SPLIT=pd.Timestamp("2020-01-01"); COST=2.5
d=pd.read_csv(F); d["dt"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
c=d["close"].to_numpy(); dt=d["dt"].to_numpy(); n=len(c)
def rollpct(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        w=x[max(0,i-W+1):i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=100*(w<=x[i]).mean()
    return out
def bt(MAW,WIN,MAXH):
    ma=pd.Series(c).rolling(MAW).mean().to_numpy(); dist=(c-ma)/ma*100.0; osc=rollpct(dist,WIN)
    trades=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        dr=+1 if osc[i]<LO else (-1 if osc[i]>HI else 0)
        if dr==0: i+=1; continue
        entry=c[i]; j=i
        for k in range(i+1,min(i+1+MAXH,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (dr>0 and osc[k]>=EXIT) or (dr<0 and osc[k]<=EXIT): break
        trades.append((dt[j],(c[j]-entry)/PIP*dr-COST)); i=j+1
    return trades
def rep(ts):
    if len(ts)<10: return f"N={len(ts)}(pochi)"
    p=np.array([t[1] for t in ts]); neg=p[p<0]
    pf=p[p>0].sum()/-neg.sum() if neg.sum()!=0 else 9.99
    sd=p.std(ddof=1); t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
    eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
    return f"N={len(p):4d} EV={p.mean():+5.1f} tot={p.sum():+7.0f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f} R/DD={p.sum()/-dd if dd<0 else 9.9:.1f}"
print(f"=== GBPCHF H6 REALE | sweep orizzonte | costo {COST}pip | 4 barre/giorno ===\n")
for lbl,MAW,WIN,MAXH in [("7gg (EURGBP-H6)",28,280,48),("14gg",56,560,96),
                          ("21gg",84,756,180),("28gg (edge D1)",112,1008,240),
                          ("40gg",160,1440,320)]:
    ts=bt(MAW,WIN,MAXH); tr=[t for t in ts if t[0]<SPLIT]; te=[t for t in ts if t[0]>=SPLIT]
    print(f"  {lbl:18s} MA{MAW} WIN{WIN}")
    print(f"     TRAIN {rep(tr)}")
    print(f"     TEST  {rep(te)}")
