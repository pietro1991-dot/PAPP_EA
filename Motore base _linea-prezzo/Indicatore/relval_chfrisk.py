#!/usr/bin/env python3
"""
relval_chfrisk.py - Verifica il RISCHIO CODA CHF (shock SNB 15-01-2015) sulle reversioni
EURCHF/GBPCHF. Riusa la logica di relval.py: estraggo i trade, la peggior perdita singola,
e ogni trade che ATTRAVERSA gennaio 2015. Se la reversione era short-CHF (long EURCHF) nel
gap, sarebbe esplosa. Voglio i numeri veri, non assunzioni.
"""
import numpy as np, pandas as pd
BASE="../"
P={"EURUSD":BASE+"EURUSD/PAPP_Export.csv","GBPUSD":BASE+"GBPUSD/PAPP_Export_GBPUSD.csv","USDCHF":BASE+"USDCHF/PAPP_Export_USDCHF.csv"}
WIN=252;LO=10;HI=90;HOLD_MAX=60;MAWIN=28;COST=1.5
def load(p):
    d=pd.read_csv(p);d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":p}).set_index("datetime")
def rollpct(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        w=x[max(0,i-W+1):i+1];w=w[~np.isnan(w)]
        if len(w)>=30:out[i]=100*(w<=x[i]).mean()
    return out
def bt(price,dtidx,name):
    n=len(price);c=price;pip=0.0001
    ma=pd.Series(c).rolling(MAWIN).mean().to_numpy();dist=(c-ma)/ma*100;osc=rollpct(dist,WIN)
    trades=[];i=0
    while i<n-1:
        if np.isnan(osc[i]):i+=1;continue
        d=+1 if osc[i]<LO else(-1 if osc[i]>HI else 0)
        if d==0:i+=1;continue
        entry=c[i];ei=i;j=i
        for k in range(i+1,min(i+1+HOLD_MAX,n)):
            j=k
            if np.isnan(osc[k]):continue
            if(d==+1 and osc[k]>=50)or(d==-1 and osc[k]<=50):break
        pnl=(c[j]-entry)/pip*d-COST
        trades.append((dtidx[ei],dtidx[j],d,entry,c[j],pnl));i=j+1
    p=np.array([t[5] for t in trades])
    worst=min(trades,key=lambda t:t[5])
    print(f"\n  {name}: N={len(trades)} tot={p.sum():+.0f} peggior_trade={worst[5]:+.0f}pip ({worst[0].date()}->{worst[1].date()} dir={'LONG' if worst[2]>0 else 'SHORT'})")
    # trade che attraversano gennaio 2015
    g0=pd.Timestamp("2014-12-15");g1=pd.Timestamp("2015-02-15")
    span=[t for t in trades if t[0]<=g1 and t[1]>=g0]
    if span:
        for t in span:
            print(f"    SHOCK-WINDOW: {t[0].date()}->{t[1].date()} dir={'LONG' if t[2]>0 else 'SHORT'} entry={t[3]:.4f} exit={t[4]:.4f} pnl={t[5]:+.0f}pip")
    else:
        print(f"    nessun trade aperto nella finestra 15-dic-2014 / 15-feb-2015 (la reversione NON era posizionata nel gap)")
df=load(P["EURUSD"]).join(load(P["GBPUSD"]),how="inner").join(load(P["USDCHF"]),how="inner").dropna().sort_index()
eur=df[P["EURUSD"]].to_numpy();gbp=df[P["GBPUSD"]].to_numpy();chf=df[P["USDCHF"]].to_numpy();idx=df.index
print(f"=== RISCHIO CHF (shock SNB 15-01-2015) | barre={len(df)} | config tipo-EA ===")
bt(eur*chf,idx,"EURCHF")
bt(gbp*chf,idx,"GBPCHF")
# valore EURCHF attorno allo shock
mask=(idx>=pd.Timestamp("2015-01-10"))&(idx<=pd.Timestamp("2015-01-20"))
ec=eur*chf
print("\n  EURCHF sintetico attorno allo shock:")
for t,v in zip(idx[mask],ec[mask]):print(f"    {t.date()}: {v:.4f}")
