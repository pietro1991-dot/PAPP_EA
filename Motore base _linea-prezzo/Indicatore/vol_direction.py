#!/usr/bin/env python3
"""
vol_direction.py - La volatilita' predice la DIREZIONE del prezzo?

Testa due canali reali, cross-strumento, corretto per il drift di periodo,
split train/test:
  A) RISK-OFF: vol alta -> EUR/GBP giu' (USD rifugio)? rendimento con segno per
     stato di vol (alta/bassa).
  B) ESPANSIONE: vol in salita -> il prezzo CONTINUA nel verso del momentum recente?
     rendimento orientato col segno del momentum, condizionato a vol in espansione.

Edge = stesso segno su train E test E su tutti gli strumenti, |valore|>spread.
Usa l'export D1 (close + vol% / volPct). Vol "viva" = std dei rendimenti close.
"""
import argparse
import numpy as np
import pandas as pd

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    ap.add_argument("--horizons", default="1,5,10,20")
    ap.add_argument("--volwin", type=int, default=20)
    return ap.parse_args()

def analyze(path, H, cost, train_pct, volwin):
    df=pd.read_csv(path); df["datetime"]=pd.to_datetime(df["datetime"],format="%Y.%m.%d %H:%M")
    df=df.sort_values("datetime").reset_index(drop=True)
    pip=0.0001; c=df["close"].to_numpy(); n=len(df)
    logc=np.log(c); r=np.empty(n); r[0]=0; r[1:]=logc[1:]-logc[:-1]
    rv=pd.Series(r).rolling(volwin,min_periods=volwin//2).std().to_numpy()      # vol viva
    rv_long=pd.Series(r).rolling(volwin*5,min_periods=volwin).std().to_numpy()
    fwd={h: np.concatenate([(c[h:]-c[:-h])/pip, np.full(h,np.nan)]) for h in H}
    mom=np.full(n,np.nan); mom[5:]=np.sign(c[5:]-c[:-5])                         # segno momentum 5 barre
    split=int(n*train_pct); arange=np.arange(n)
    base={h:{} for h in H}
    for h in H:
        for nm,msk in [("tr",arange<split),("te",arange>=split)]:
            x=fwd[h][msk]; x=x[~np.isnan(x)]; base[h][nm]=x.mean()
    # percentile vol viva (trailing 252)
    W=252; volp=np.full(n,np.nan)
    for i in range(n):
        lo=max(0,i-W+1); w=rv[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: volp[i]=(w<=rv[i]).mean()
    out={}
    def cells(mask, orient):
        res=[]
        for h in H:
            row=[]
            for nm,msk in [("tr",arange<split),("te",arange>=split)]:
                idx=mask & msk
                x=(fwd[h]*orient)[idx]; x=x[~np.isnan(x)]
                base_adj = base[h][nm]*(np.nanmean(orient[idx]) if hasattr(orient,'__len__') else orient)
                row.append((len(x), x.mean()-base[h][nm] if not hasattr(orient,'__len__') else x.mean()))
            res.append((h,row))
        return res
    # A) risk-off: vol alta/bassa, rendimento GREZZO con segno (orient=+1) drift-corretto
    A_hi=cells(volp>0.80, +1); A_lo=cells(volp<0.20, +1)
    # B) espansione: rv in salita (rv>rv_long) + orient = momentum (continuazione)
    exp = (rv>rv_long) & ~np.isnan(mom)
    B=[]
    for h in H:
        row=[]
        for nm,msk in [("tr",arange<split),("te",arange>=split)]:
            idx=exp & msk & ~np.isnan(mom)
            x=(fwd[h]*mom)[idx]; x=x[~np.isnan(x)]
            row.append((len(x), x.mean()))      # momentum-oriented, no drift subtract (orientato)
        B.append((h,row))
    return A_hi,A_lo,B,base

def main():
    a=parse_args(); H=[int(x) for x in a.horizons.split(",")]; cost=a.spread_pip
    print(f"\n=== VOLATILITA' -> DIREZIONE | spread {cost}pip | drift-corretto, train/test ===")
    for path in a.csvs:
        name=path.split("/")[-1]
        A_hi,A_lo,B,base=analyze(path,H,cost,a.train_pct,a.volwin)
        print(f"\n----- {name} -----")
        print("  drift:", " ".join(f"+{h}b tr{base[h]['tr']:+.1f}/te{base[h]['te']:+.1f}" for h in H))
        def show(tag,data):
            s=[]
            for h,row in data:
                (ntr,mtr),(nte,mte)=row
                s.append(f"+{h}b:{mtr:+5.1f}/{mte:+5.1f}")
            print(f"  {tag:30s} " + "  ".join(s))
        print("  A) RISK-OFF (rendimento con segno, drift-corretto):")
        show("vol ALTA(>80) ->",A_hi)
        show("vol BASSA(<20) ->",A_lo)
        print("  B) ESPANSIONE (rendimento orientato col momentum = continuazione):")
        show("vol in salita x momentum ->",B)
    print("\nEdge = stesso segno e |valore|>spread su train E test E tutti gli strumenti.\n")

if __name__=="__main__":
    main()
