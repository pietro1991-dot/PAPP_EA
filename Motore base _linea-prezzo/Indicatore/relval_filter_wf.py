#!/usr/bin/env python3
"""
relval_filter_wf.py - Walk-forward ONESTO del filtro trend (Efficiency Ratio) su EURGBP D1.
Taro (er,ern) sul TRAIN (<2020) per miglior profitto, poi guardo il TEST (>=2020).
Stampa la griglia train/test per ogni config + qual e' la train-best e come va sul test.
Se la train-best e' buona anche sul test -> il filtro generalizza. Altrimenti = overfit.
"""
import numpy as np, pandas as pd
BASE="../"; pip=0.0001; COST=2.5; MAWIN=30; HOLD=60; LO=20; HI=80; WIN=252
SPLIT=pd.Timestamp("2020-01-01")
ERS=[0.20,0.25,0.30,0.35,0.40,1.0]   # 1.0 = nessun filtro (plain)
ERNS=[15,20,25]
def L(p,nm):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":nm}).set_index("datetime")
df=L(BASE+"EURUSD/PAPP_Export.csv","EUR").join(L(BASE+"GBPUSD/PAPP_Export_GBPUSD.csv","GBP"),how="inner").dropna().sort_index()
px=(df["EUR"]/df["GBP"]).to_numpy(); dates=df.index; n=len(px)
ma=pd.Series(px).rolling(MAWIN).mean().to_numpy(); dist=(px-ma)/ma*100.0
osc=np.full(n,np.nan)
for i in range(n):
    lo=max(0,i-WIN+1); w=dist[lo:i+1]; w=w[~np.isnan(w)]
    if len(w)>=30: osc[i]=100*(w<=dist[i]).mean()
ch=np.abs(np.diff(px,prepend=px[0]))
def er_series(ern):
    er=np.full(n,np.nan)
    for i in range(ern,n):
        den=ch[i-ern+1:i+1].sum(); er[i]=abs(px[i]-px[i-ern])/den if den>0 else 0.0
    return er
def bt(er_arr,erthr):
    tr=[]; td=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<LO else (-1 if osc[i]>HI else 0)
        if d==0: i+=1; continue
        if erthr<1.0 and (np.isnan(er_arr[i]) or er_arr[i]>=erthr): i+=1; continue
        entry=px[i]; j=i
        for k in range(i+1,min(i+1+HOLD,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d>0 and osc[k]>=50) or (d<0 and osc[k]<=50): break
        tr.append((px[j]-entry)/pip*d-COST); td.append(dates[i]); i=j+1
    return np.array(tr), pd.to_datetime(td)
def metr(p):
    if len(p)<5: return (len(p),0,0,0)
    eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
    return (len(p), p.sum(), p.sum()/-dd if dd<0 else 9.9, p[p>0].sum()/-p[p<0].sum() if p[p<0].sum()!=0 else 9.9)
print(f"\n=== WALK-FORWARD FILTRO TREND | EURGBP D1 | train<2020 / test>=2020 ===")
print(f"{'ern':>4}{'erThr':>7} | {'TRAIN N/tot/RDD/PF':>26} | {'TEST N/tot/RDD/PF':>26}")
best=None
for ern in ERNS:
    er=er_series(ern)
    for erthr in ERS:
        p,td=bt(er,erthr); m=td<SPLIT
        tr=metr(p[m]); te=metr(p[~m])
        tag="  <plain>" if erthr>=1.0 else ""
        print(f"{ern:>4}{erthr:>7.2f} | N{tr[0]:3d} {tr[1]:+6.0f} {tr[2]:4.1f} {tr[3]:4.2f}        | N{te[0]:3d} {te[1]:+6.0f} {te[2]:4.1f} {te[3]:4.2f}{tag}")
        if erthr<1.0 and tr[0]>=40 and (best is None or tr[1]>best[2]):
            best=(ern,erthr,tr[1],tr,te)
print()
if best:
    ern,erthr,_,tr,te=best
    print(f">>> TRAIN-BEST: ern={ern} erThr={erthr}  -> TRAIN tot {tr[1]:+.0f} (RDD {tr[2]:.1f})  TEST tot {te[1]:+.0f} (RDD {te[2]:.1f}, PF {te[3]:.2f}, N {te[0]})")
    # confronto: plain sul test
    erp=er_series(20); pp,tdp=bt(erp,1.0); mp=tdp<SPLIT; pte=metr(pp[~mp])
    print(f">>> PLAIN sul TEST: tot {pte[1]:+.0f} (RDD {pte[2]:.1f}, PF {pte[3]:.2f}, N {pte[0]})")
    print(">>> Il filtro GENERALIZZA solo se TEST-filtro batte TEST-plain.")
print()
