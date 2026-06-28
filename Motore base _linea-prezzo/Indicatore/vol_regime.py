#!/usr/bin/env python3
"""
vol_regime.py - Le ALTRE linee danno la direzione quando la vol e' alta?

Ipotesi: vol alta = "movimento grosso in arrivo"; la DIREZIONE la da' la velocita'
della struttura (pendenza mediana). Trend forte -> continua (follow); struttura
piatta -> reversione (fade). Testa SOLO sugli eventi ad alta vol, cross-strumento,
trade NON sovrapposti, split train/test.

Uso: python3 vol_regime.py <csv...> --volthr=0.7 --hold=10 --mode=follow|fade
"""
import argparse
import numpy as np
import pandas as pd

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--volthr", type=float, default=0.70)
    ap.add_argument("--hold", type=int, default=10)
    ap.add_argument("--mode", choices=["follow","fade"], default="follow")
    ap.add_argument("--velmin", type=float, default=0.0, help="usa solo se |velP|>velmin (trend forte)")
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def rollpct(vals, use_abs, Wp=252):
    x=np.abs(vals) if use_abs else vals.astype(float); out=np.full(len(x),np.nan)
    for i in range(len(x)):
        lo=max(0,i-Wp+1); w=x[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=(w<=x[i]).mean()
    return out

def run(path, a):
    df=pd.read_csv(path); df["datetime"]=pd.to_datetime(df["datetime"],format="%Y.%m.%d %H:%M")
    df=df.sort_values("datetime").reset_index(drop=True)
    pip=0.0001; c=df["close"].to_numpy(); n=len(df)
    med=df["median"].to_numpy(); K=5
    vraw=np.full(n,np.nan); vraw[K:]=(med[K:]-med[:-K])/med[:-K]*100.0
    sgnV=np.sign(vraw); velP=rollpct(vraw,True)
    if "volPct" in df.columns: volP=df["volPct"].to_numpy()
    else: volP=rollpct(df["vol%"].to_numpy(),False)
    split=int(n*a.train_pct); cost=a.spread_pip
    sign=+1 if a.mode=="follow" else -1
    trades=[]; i=0
    while i<n-a.hold:
        ok = (not np.isnan(volP[i]) and volP[i]>a.volthr and sgnV[i]!=0
              and (np.isnan(velP[i])==False and velP[i]>a.velmin))
        if ok:
            d=int(sign*sgnV[i]); j=i+a.hold
            trades.append((j,(c[j]-c[i])/pip*d - cost)); i=j
        else: i+=1
    def rep(ts):
        if len(ts)<10: return f"N={len(ts)} (pochi)"
        p=np.array([t[1] for t in ts]); w=p[p>0]; l=p[p<0]
        pf=w.sum()/-l.sum() if l.sum()!=0 else 9.99
        sd=p.std(ddof=1) if len(p)>1 else 0; t=p.mean()/(sd/np.sqrt(len(p))) if sd>0 else 0
        return f"N={len(p):4d} EV={p.mean():+5.1f} PF={pf:.2f} win={(p>0).mean()*100:3.0f}% t={t:+.2f}"
    return rep([t for t in trades if t[0]<split]), rep([t for t in trades if t[0]>=split])

def main():
    a=parse_args()
    print(f"\n=== VOL alta + velocita' = direzione | mode={a.mode} volthr={a.volthr} "
          f"velmin={a.velmin} hold={a.hold} spread={a.spread_pip} ===")
    for path in a.csvs:
        tr,te=run(path,a)
        print(f"  {path.split('/')[-1]:28s} TRAIN[{tr}]  TEST[{te}]")
    print("  Edge = EV>0, PF>1, stesso segno su TRAIN+TEST e su TUTTI gli strumenti.\n")

if __name__=="__main__":
    main()
