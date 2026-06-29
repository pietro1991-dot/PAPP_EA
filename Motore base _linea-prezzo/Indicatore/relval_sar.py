#!/usr/bin/env python3
"""
relval_sar.py - Stop-and-Reverse sul relative-value EURGBP.
Idea utente: quando la reversione va contro (sta TRENDANDO), invece di subire,
chiudi e INVERTI cavalcando il trend. Confronta:
  PLAIN : reversione pura (entra estremo, esci al centro / maxhold)
  SAR   : se la perdita raggiunge SARpips, chiudi e apri la direzione opposta (trend),
          esci quando l'osc torna verso il centro (trend esaurito) o maxhold.
Trade NON sovrapposti, costo, P&L totale + drawdown + anno per anno.
Uso: python3 relval_sar.py [--sar=120] [--cost=2.5] [--mawin=30] [--lo=20] [--hold=60]
"""
import argparse
import numpy as np
import pandas as pd

BASE="../"
ap=argparse.ArgumentParser()
ap.add_argument("--sar",type=float,default=120)   # pip di escursione avversa che fa scattare l'inversione
ap.add_argument("--cost",type=float,default=2.5)
ap.add_argument("--mawin",type=int,default=30); ap.add_argument("--lo",type=float,default=20)
ap.add_argument("--hold",type=int,default=60)
ap.add_argument("--stop",type=float,default=0)  # stop secco in pip (0=off), niente inversione
ap.add_argument("--tf",default="D1")    # D1 (export) oppure H4/H6/H8 (da OHLC H1 ricampionato)
ap.add_argument("--pair",default="EURGBP")  # EURGBP (cross) | EURUSD | GBPUSD (singoli)
a=ap.parse_args()
WIN=252; HI=100-a.lo; pip=0.0001
_RULE={"H4":"4h","H6":"6h","H8":"8h"}
_H1={"EURUSD":BASE+"EURUSD/OHLC_EURUSD_H1.csv","GBPUSD":BASE+"GBPUSD/OHLC_GBPUSD_H1.csv"}
_D1={"EURUSD":BASE+"EURUSD/PAPP_Export.csv","GBPUSD":BASE+"GBPUSD/PAPP_Export_GBPUSD.csv"}

def _load(p,nm):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":nm}).set_index("datetime")

def cross_series():
    src=_D1 if a.tf=="D1" else _H1
    if a.pair in ("EURUSD","GBPUSD"):
        df=_load(src[a.pair],"P").dropna().sort_index()
        if a.tf!="D1": df=df.resample(_RULE[a.tf]).agg(P=("P","last")).dropna()
        return df["P"].to_numpy(), df.index.to_numpy()
    # EURGBP cross
    df=_load(src["EURUSD"],"EUR").join(_load(src["GBPUSD"],"GBP"),how="inner").dropna().sort_index()
    if a.tf!="D1": df=df.resample(_RULE[a.tf]).agg(EUR=("EUR","last"),GBP=("GBP","last")).dropna()
    return (df["EUR"]/df["GBP"]).to_numpy(), df.index.to_numpy()

def rollpct_signed(x,W):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-W+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=100*(w<=x[i]).mean()
    return out

def stats(pnls, dates, label):
    if not pnls: print(f"  {label}: nessun trade"); return
    p=np.array(pnls); eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
    s=pd.Series(p,index=pd.to_datetime(dates)); yr=s.groupby(s.index.year).sum()
    pf=p[p>0].sum()/-p[p<0].sum() if p[p<0].sum()!=0 else 9.99
    print(f"  {label}: tot={p.sum():+.0f}pip PF={pf:.2f} maxDD={dd:+.0f} R/DD={p.sum()/-dd if dd<0 else 9.9:.1f} N={len(p)} anni+={int((yr>0).sum())}/{len(yr)}")
    print(f"    per anno: "+" ".join(f"{y}:{int(v):+d}" for y,v in yr.items()))

def run(close, osc, sar_on):
    n=len(close); trades=[]; tdate=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<a.lo else (-1 if osc[i]>HI else 0)
        if d==0: i+=1; continue
        entry=close[i]; di=i; reversed_once=False; pos=d
        j=i
        for k in range(i+1,min(i+1+a.hold,n)):
            j=k
            move=(close[k]-entry)/pip*pos
            if a.stop>0 and (not reversed_once) and move<=-a.stop:
                break    # STOP secco: esci in perdita (niente inversione)
            if (not reversed_once) and sar_on and move<=-a.sar:
                # chiudi reversione in perdita REALE (move, non -sar idealizzato), INVERTI
                trades.append(move - a.cost); tdate.append(d_idx_time[di])
                pos=-pos; entry=close[k]; di=k; reversed_once=True
                continue
            # uscita: osc torna al centro nella direzione della posizione corrente
            if (pos>0 and osc[k]>=50) or (pos<0 and osc[k]<=50):
                break
        trades.append((close[j]-entry)/pip*pos - a.cost); tdate.append(d_idx_time[di]); i=j+1
    return trades,tdate

px,d_idx_time=cross_series()
ma=pd.Series(px).rolling(a.mawin).mean().to_numpy()
osc=rollpct_signed((px-ma)/ma*100.0,WIN)
print(f"\n=== {a.pair} relval STOP-AND-REVERSE | TF={a.tf} sar={a.sar}pip cost={a.cost} ma={a.mawin} hold={a.hold} ===")
tp,td=run(px,osc,False); stats(tp,td,"PLAIN  ")
ts,ts_d=run(px,osc,True); stats(ts,ts_d,"SAR    ")
print()
