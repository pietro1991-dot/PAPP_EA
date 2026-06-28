#!/usr/bin/env python3
"""
single_line_bt.py - Backtest NON SOVRAPPOSTO di una singola linea come entrata.
Arbitra i candidati 'robusti' di line_forward senza l'inganno delle finestre
sovrapposte: entra sullo stato, tiene H barre, NESSUN trade sovrapposto, costo,
split train/test. Stampa EV, PF, DD su train e test.

Uso: python3 single_line_bt.py <PAPP_Export.csv> --line=Accel --state=low --dir=long --hold=10
"""
import argparse
import numpy as np
import pandas as pd

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--line", required=True, choices=["Cluster","Velocita","Accel","Volatilita","MEDIA","DistMediana"])
    ap.add_argument("--state", required=True, choices=["high","low"])
    ap.add_argument("--dir", required=True, choices=["long","short"])
    ap.add_argument("--hold", type=int, default=10)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def main():
    a=parse_args()
    df=pd.read_csv(a.csv); df["datetime"]=pd.to_datetime(df["datetime"],format="%Y.%m.%d %H:%M")
    df=df.sort_values("datetime").reset_index(drop=True)
    pip=0.0001; c=df["close"].to_numpy(); n=len(df)
    def rollpct(vals, use_abs, Wp=252):
        x=np.abs(vals) if use_abs else vals.astype(float); out=np.full(len(x),np.nan)
        for i in range(len(x)):
            lo=max(0,i-Wp+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
            if len(w)>=30: out[i]=(w<=x[i]).mean()
        return out
    # Velocita'/Accel dalla FONTE VERA = pendenza della mediana (il vel%/acc% degli
    # export vecchi GBP/CHF e' senza segno). K=5 come KSLOPE dell'indicatore.
    med=df["median"].to_numpy(); K=5
    vraw=np.full(n,np.nan); vraw[K:]=(med[K:]-med[:-K])/med[:-K]*100.0
    araw=np.full(n,np.nan); araw[2*K:]=(med[2*K:]-2.0*med[K:-K]+med[:-2*K])/med[:-2*K]*100.0
    sgnV=np.sign(vraw); sgnA=np.sign(araw)
    velP=rollpct(vraw,True); accP=rollpct(araw,True)
    if "cluPct" in df.columns:
        cluP=df["cluPct"].to_numpy(); volP=df["volPct"].to_numpy()
    else:
        cluP=rollpct(df["cluster%"].to_numpy(),False); volP=rollpct(df["vol%"].to_numpy(),False)
    dMed=df["dMed%"].to_numpy()
    W=252; osc=np.full(n,np.nan)
    for i in range(n):
        lo=max(0,i-W+1); w=dMed[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: osc[i]=100*(w<=dMed[i]).mean()
    L={"Cluster":cluP*100,"Velocita":50+sgnV*velP*50,"Accel":50+sgnA*accP*50,
       "Volatilita":volP*100,"MEDIA":np.nanmean(np.vstack([cluP,velP,accP,volP]),axis=0)*100,
       "DistMediana":osc}[a.line]
    d=+1 if a.dir=="long" else -1
    cond = (L>80) if a.state=="high" else (L<20)
    split=int(n*a.train_pct); cost=a.spread_pip

    trades=[]; i=0
    while i < n-a.hold:
        if not np.isnan(L[i]) and cond[i]:
            j=i+a.hold
            pnl=(c[j]-c[i])/pip*d - cost
            trades.append((j,pnl)); i=j        # non sovrapposto
        else:
            i+=1
    def rep(name,ts):
        if len(ts)<10: print(f"  {name}: N={len(ts)} (pochi)"); return
        p=np.array([t[1] for t in ts]); w=p[p>0]; l=p[p<0]
        pf=w.sum()/-l.sum() if l.sum()!=0 else float('inf')
        eq=np.cumsum(p); dd=(eq-np.maximum.accumulate(eq)).min()
        sd=p.std(ddof=1) if len(p)>1 else 0
        t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
        print(f"  {name}: N={len(p):4d}  EV={p.mean():+5.2f}  tot={p.sum():+7.0f}  win={(p>0).mean()*100:3.0f}%  PF={pf:.2f}  t={t:+.2f}  maxDD={dd:+6.0f}")
    print(f"\n=== {a.line} {a.state} -> {a.dir}, hold {a.hold}, NON sovrapposto | spread {cost} ===")
    rep("TRAIN",[t for t in trades if t[0]<split])
    rep("TEST ",[t for t in trades if t[0]>=split])
    rep("TUTTO",trades)
    print()

if __name__=="__main__":
    main()
