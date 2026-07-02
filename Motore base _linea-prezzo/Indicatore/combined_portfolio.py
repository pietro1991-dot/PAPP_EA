#!/usr/bin/env python3
"""
combined_portfolio.py - DECORRELAZIONE: EURUSD-base + EURGBP-relval (file nuovo, non tocca l'EA).

Domanda: mettere insieme il motore base EURUSD (skew-negativo, Ret/DD-soldi ~1) e l'edge
relative-value EURGBP (reversione ortogonale, [[relval-edge]]) alza il Ret/DD del PORTAFOGLIO
per decorrelazione? Se le due equity sono poco correlate, il DD combinato < media dei DD.

Problema unita': il base e' in R (ha SL -> rischio definito), il relval e' in pip (reversione
senza SL). Confronto ONESTO e unita'-indipendente: porto entrambe a RENDIMENTI MENSILI, scalo
ciascuna a volatilita' mensile unitaria (pari rischio), combino 50/50. La decorrelazione si
legge da: correlazione mensile, Sharpe (mean/std*sqrt12), MaxDD e Ret/DD su equity a pari-vol.

Base = 6 pattern P1-P6 (BASE variant di exit_grid_R, 1 pos/volta, guardie EA).
Relval = cross sintetico EURGBP = EURUSD/GBPUSD, reversione osc<20/>80 -> centro (relval.py).
Date allineate (inner join). Split TRAIN<2020 / TEST>=2020 mostrato a parte.
"""
import numpy as np, pandas as pd
import pattern_mining as pm

BASE="../"; SPLIT="2020-01-01"; SPREAD=15
PATTERNS=[("P1","MA30",-1,"MA365",15),("P2","MA121",1,"MA365",15),
          ("P3","MA365",-1,"MA121",12),("P4","MA7",-1,"MA365",12),
          ("P5","MA30",1,"MA365",15),("P6","MA14",1,"MA365",15)]

# ---------- 1) BASE EURUSD: trade in R con data di uscita ----------
def base_trades():
    rows=pm.load_csv(BASE+"EURUSD/PAPP_Export.csv")
    ents=pm.detect_entries(rows); idx_by={}
    for e in ents: idx_by.setdefault((e['line'],e['dir']),[]).append(e)
    evs=[]
    for name,entry,d,sl,tp in PATTERNS:
        sl_col=pm.LINE_COLS[pm.LINE_NAMES.index(sl)]; buy=(d==1)
        for e in idx_by.get((entry,d),[]):
            i=e['idx']
            try: sv=float(rows[i][sl_col])
            except: continue
            if not(0<sv<1e12): continue
            if buy and sv>=e['price']: continue
            if (not buy) and sv<=e['price']: continue
            if abs(e['price']-sv)/pm.PT_SIZE < 50: continue
            evs.append({'idx':i,'buy':buy,'price':e['price'],'sl_col':sl_col,'tp':tp})
    evs.sort(key=lambda x:x['idx'])
    out=[]; last=-1
    for ev in evs:
        if ev['idx']<=last: continue
        o=pm.simulate_trade(rows,ev['idx'],ev['buy'],ev['price'],ev['sl_col'],ev['tp'],SPREAD)
        if o is None: continue
        pnl,_,ex,_=o; risk=abs(ev['price']-float(rows[ev['idx']][ev['sl_col']]))/pm.PT_SIZE
        if risk<=0: continue
        out.append((pd.to_datetime(rows[ex]['datetime'],format="%Y.%m.%d %H:%M"), pnl/risk))
        last=ex
    return pd.DataFrame(out,columns=["dt","pnl"]).set_index("dt")["pnl"]

# ---------- 2) RELVAL EURGBP: cross sintetico, reversione (in pip) ----------
def load_close(p):
    d=pd.read_csv(p); d["datetime"]=pd.to_datetime(d["datetime"],format="%Y.%m.%d %H:%M")
    return d[["datetime","close"]].rename(columns={"close":"c"}).set_index("datetime")["c"]

def rollpct_signed(x,W=252):
    out=np.full(len(x),np.nan)
    for i in range(len(x)):
        w=x[max(0,i-W+1):i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: out[i]=100*(w<=x[i]).mean()
    return out

def relval_trades(mawin=30,LO=20,HOLD=60,COST=1.0):
    eur=load_close(BASE+"EURUSD/PAPP_Export.csv"); gbp=load_close(BASE+"GBPUSD/PAPP_Export_GBPUSD.csv")
    df=pd.concat({"e":eur,"g":gbp},axis=1).dropna()
    cross=(df["e"]/df["g"]); idx=cross.index; c=cross.to_numpy(); pip=0.0001; HI=100-LO
    ma=pd.Series(c).rolling(mawin).mean().to_numpy(); dist=(c-ma)/ma*100.0
    osc=rollpct_signed(dist); n=len(c); trades=[]; i=0
    while i<n-1:
        if np.isnan(osc[i]): i+=1; continue
        d=+1 if osc[i]<LO else (-1 if osc[i]>HI else 0)
        if d==0: i+=1; continue
        entry=c[i]; j=i
        for k in range(i+1,min(i+1+HOLD,n)):
            j=k
            if np.isnan(osc[k]): continue
            if (d==+1 and osc[k]>=50) or (d==-1 and osc[k]<=50): break
        trades.append((idx[j],(c[j]-entry)/pip*d-COST)); i=j+1
    return pd.DataFrame(trades,columns=["dt","pnl"]).set_index("dt")["pnl"]

# ---------- 3) mensile, pari-vol, combinato ----------
def monthly(s): return s.groupby(pd.Grouper(freq="ME")).sum()

def stats(m):
    if m.std()==0 or len(m)<6: return None
    eq=m.cumsum(); peak=eq.cummax(); dd=(peak-eq).max()
    sharpe=m.mean()/m.std()*np.sqrt(12)
    return {'mean':m.mean(),'std':m.std(),'sharpe':sharpe,'tot':eq.iloc[-1],'mdd':dd,
            'retdd':(eq.iloc[-1]/dd if dd>0 else float('inf')),'n':len(m)}

def show(label, a, b):
    """a,b = serie mensili GIA' a pari-vol (std 1)."""
    comb=0.5*a+0.5*b
    corr=a.corr(b)
    print(f"\n  === {label} ===  correlazione mensile base<->relval = {corr:+.2f}")
    print(f"  {'serie':<16} {'Sharpe':>7} {'Tot(vol-unit)':>13} {'MaxDD':>7} {'Ret/DD':>7} {'mesi':>5}")
    for nm,s in (("EURUSD base",a),("EURGBP relval",b),("COMBINATO 50/50",comb)):
        st=stats(s)
        if not st: print(f"  {nm:<16} n/a"); continue
        rd=f"{st['retdd']:>7.2f}" if st['retdd']!=float('inf') else "    inf"
        print(f"  {nm:<16} {st['sharpe']:>7.2f} {st['tot']:>+13.1f} {st['mdd']:>7.1f} {rd} {st['n']:>5}")

def main():
    print("Carico serie trade...")
    b=monthly(base_trades()); r=monthly(relval_trades())
    df=pd.concat({"base":b,"rel":r},axis=1).dropna()
    print(f"mesi comuni con attivita' su entrambe: {len(df)}  ({df.index.min():%Y-%m} -> {df.index.max():%Y-%m})")
    # pari-vol sull'INTERO periodo (scala unica, no look-ahead di regime)
    a_all=df["base"]/df["base"].std(); r_all=df["rel"]/df["rel"].std()
    show("PERIODO INTERO", a_all, r_all)
    # split
    tr=df.index<SPLIT; te=df.index>=SPLIT
    show("TRAIN <2020", (df["base"][tr]/df["base"][tr].std()), (df["rel"][tr]/df["rel"][tr].std()))
    show("TEST >=2020", (df["base"][te]/df["base"][te].std()), (df["rel"][te]/df["rel"][te].std()))
    print("\nLettura: se correlazione ~0 (o <0) e il Ret/DD COMBINATO > di ENTRAMBI i singoli,")
    print("la decorrelazione crea valore reale a parita' di rischio. Se corr alta, poco guadagno.")

if __name__=="__main__": main()
