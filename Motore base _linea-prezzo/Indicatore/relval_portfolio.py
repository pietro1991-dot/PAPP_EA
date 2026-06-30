#!/usr/bin/env python3
"""
relval_portfolio.py - DECORRELAZIONE del basket di reversioni (EURGBP/EURCHF/GBPCHF).
I tre cross condividono le gambe: aggiungerli diversifica o moltiplica solo il rischio?
Aggrego il P&L di ogni strategia per MESE, correlazioni a coppie, e confronto il
portafoglio combinato (equal weight) coi singoli su R/DD e worst-month.
Config tipo-EA. Dati D1.
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
def trades_of(price,dtidx):
    n=len(price);c=price;pip=0.0001
    ma=pd.Series(c).rolling(MAWIN).mean().to_numpy();dist=(c-ma)/ma*100;osc=rollpct(dist,WIN)
    tr=[];i=0
    while i<n-1:
        if np.isnan(osc[i]):i+=1;continue
        d=+1 if osc[i]<LO else(-1 if osc[i]>HI else 0)
        if d==0:i+=1;continue
        entry=c[i];j=i
        for k in range(i+1,min(i+1+HOLD_MAX,n)):
            j=k
            if np.isnan(osc[k]):continue
            if(d==+1 and osc[k]>=50)or(d==-1 and osc[k]<=50):break
        tr.append((dtidx[j],(c[j]-entry)/pip*d-COST));i=j+1
    return tr
def monthly(tr):
    s=pd.Series({t[0]:t[1] for t in []})  # placeholder
    df=pd.DataFrame(tr,columns=["dt","pnl"]);df["m"]=df["dt"].dt.to_period("M")
    return df.groupby("m")["pnl"].sum()
def stats(series):
    p=series.values;eq=np.cumsum(p);dd=(eq-np.maximum.accumulate(eq)).min()
    pf=p[p>0].sum()/-p[p<0].sum() if p[p<0].sum()!=0 else 9.99
    return dict(tot=p.sum(),pf=pf,dd=dd,rdd=(p.sum()/-dd if dd<0 else 9.9),worst=p.min(),
                sharpe=(p.mean()/p.std()*np.sqrt(12) if p.std()>0 else 0))
df=load(P["EURUSD"]).join(load(P["GBPUSD"]),how="inner").join(load(P["USDCHF"]),how="inner").dropna().sort_index()
eur=df[P["EURUSD"]].to_numpy();gbp=df[P["GBPUSD"]].to_numpy();chf=df[P["USDCHF"]].to_numpy();idx=df.index
M={"EURGBP":monthly(trades_of(eur/gbp,idx)),"EURCHF":monthly(trades_of(eur*chf,idx)),"GBPCHF":monthly(trades_of(gbp*chf,idx))}
allm=pd.DataFrame(M).fillna(0.0)
print(f"=== DECORRELAZIONE basket reversioni | mesi={len(allm)} | config tipo-EA ===\n")
print("  Correlazione P&L mensile (0=decorrelato, 1=ridondante):")
corr=allm.corr()
print(corr.round(2).to_string().replace("\n","\n    ").rjust(0))
print("\n  Singoli vs PORTAFOGLIO (equal weight):")
port=allm.sum(axis=1)
for name in ["EURGBP","EURCHF","GBPCHF"]:
    s=stats(allm[name]);print(f"    {name:9s} tot={s['tot']:+6.0f} PF={s['pf']:.2f} DD={s['dd']:+6.0f} R/DD={s['rdd']:.1f} worst_mese={s['worst']:+6.0f} Sharpe={s['sharpe']:+.2f}")
s=stats(port)
print(f"    {'PORTAFOGLIO':9s} tot={s['tot']:+6.0f} PF={s['pf']:.2f} DD={s['dd']:+6.0f} R/DD={s['rdd']:.1f} worst_mese={s['worst']:+6.0f} Sharpe={s['sharpe']:+.2f}")
avg_rdd=np.mean([stats(allm[n])['rdd'] for n in M])
print(f"\n  R/DD medio singoli={avg_rdd:.1f} vs portafoglio={s['rdd']:.1f} -> {'DIVERSIFICA (meglio)' if s['rdd']>avg_rdd else 'NON diversifica'}")
# coincidono i mesi peggiori? (rischio coda comune)
print("\n  3 mesi peggiori di ciascuno (coincidono = rischio comune):")
for name in M:
    w=allm[name].nsmallest(3);print(f"    {name}: "+", ".join(f"{p}({v:+.0f})" for p,v in w.items()))
