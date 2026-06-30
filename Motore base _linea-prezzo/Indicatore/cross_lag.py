#!/usr/bin/env python3
"""
cross_lag.py - VIA 2: informazione ORTOGONALE cross-strumento per predire EURUSD (file nuovo).
EURUSD = EUR/USD. Estraggo il FATTORE USD da GBPUSD+USDCHF (esclude EURUSD) e testo:
 (A) contemporaneo: EURUSD ~ -USD (sanity, dev'essere alto)
 (B) LEAD-LAG: il fattore USD di OGGI predice EURUSD DOMANI? (a D1 atteso ~0)
 (C) DIVERGENZA->reversione: la parte di EURUSD NON spiegata dal USD (mossa EUR-specifica)
     predice il ritorno di domani? (meccanismo relative-value)
Tutto train(<2020)/test, con t-stat (multiple testing in mente). Log-return, unita' ~bps.
"""
import math
from statistics import mean
import pattern_mining as pm
def load(path):
    d={}
    for r in pm.load_csv(path):
        try: d[r['datetime']]=math.log(float(r['close']))
        except: pass
    return d
EUR=load("../EURUSD/PAPP_Export.csv")
GBP=load("../GBPUSD/PAPP_Export_GBPUSD.csv")
CHF=load("../USDCHF/PAPP_Export_USDCHF.csv")
dates=sorted(set(EUR)&set(GBP)&set(CHF))
print(f"date allineate: {len(dates)} ({dates[0]} -> {dates[-1]})")
# log-returns (bps)
def rets(D):
    return {dates[i]:(D[dates[i]]-D[dates[i-1]])*10000 for i in range(1,len(dates))}
re=rets(EUR); rg=rets(GBP); rc=rets(CHF)
D=dates[1:]
# fattore USD: USD forte = GBPUSD giu' (-rg) e USDCHF su' (+rc)
usd={t:(-rg[t]+rc[t])/2 for t in D}
SPLIT="2020.01.01"
def corr_t(xs,ys):
    pairs=[(x,y) for x,y in zip(xs,ys) if x is not None and y is not None]
    N=len(pairs)
    if N<10: return 0,0,N
    mx=mean(p[0] for p in pairs); my=mean(p[1] for p in pairs)
    sxy=sum((p[0]-mx)*(p[1]-my) for p in pairs)
    sxx=sum((p[0]-mx)**2 for p in pairs); syy=sum((p[1]-my)**2 for p in pairs)
    if sxx<=0 or syy<=0: return 0,0,N
    r=sxy/math.sqrt(sxx*syy); t=r*math.sqrt(N-2)/math.sqrt(max(1e-9,1-r*r))
    return r,t,N
def split(seq_t, fx, fy):
    tr=([fx(t) for t in seq_t if t<SPLIT],[fy(t) for t in seq_t if t<SPLIT])
    te=([fx(t) for t in seq_t if t>=SPLIT],[fy(t) for t in seq_t if t>=SPLIT])
    return tr,te
def report(name, seq_t, fx, fy):
    (xtr,ytr),(xte,yte)=split(seq_t,fx,fy)
    rt,tt,nt=corr_t(xtr,ytr); rte,tte,nte=corr_t(xte,yte)
    flag=" <== ROBUSTO" if (rt*rte>0 and abs(tt)>2 and abs(tte)>2) else ""
    print(f"  {name:34s} TRAIN r={rt:+.3f} t={tt:+5.1f} (N{nt}) | TEST r={rte:+.3f} t={tte:+5.1f} (N{nte}){flag}")

print("\n=== (A) CONTEMPORANEO (sanity) ===")
report("EURUSD_t vs -USD_t", D, lambda t:re[t], lambda t:-usd[t])

print("\n=== (B) LEAD-LAG: USD oggi -> EURUSD domani ===")
Dl=[D[i] for i in range(len(D)-1)]; nxt={D[i]:D[i+1] for i in range(len(D)-1)}
report("USD_t -> EURUSD_t+1", Dl, lambda t:usd[t], lambda t:re[nxt[t]])
report("EURUSD_t -> EURUSD_t+1 (autocorr)", Dl, lambda t:re[t], lambda t:re[nxt[t]])

print("\n=== (C) DIVERGENZA -> reversione domani ===")
# beta stimato su TRAIN: EURUSD ~ beta*USD ; residuo = parte EUR-specifica
xt=[usd[t] for t in D if t<SPLIT]; yt=[re[t] for t in D if t<SPLIT]
mx=mean(xt); my=mean(yt)
beta=sum((a-mx)*(b-my) for a,b in zip(xt,yt))/sum((a-mx)**2 for a in xt)
print(f"  beta(EURUSD~USD)={beta:+.2f} (atteso ~ -1)")
resid={t: re[t]-beta*usd[t] for t in D}
report("residuo_t -> EURUSD_t+1", Dl, lambda t:resid[t], lambda t:re[nxt[t]])
report("residuo_t -> residuo_t+1 (rev EUR-spec)", Dl, lambda t:resid[t], lambda t:resid[nxt[t]])

print("\n=== (D) REVERSIONE MULTI-GIORNO della componente EUR-specifica (orizzonte giusto) ===")
# serie cumulativa EUR-specifica = livello sintetico; oscillatore = scostamento da MA(W)
cum={}; s=0.0
for t in D: s+=resid[t]; cum[t]=s
W=20
osc={}
for i in range(W,len(D)):
    t=D[i]; ma=mean(cum[D[j]] for j in range(i-W,i)); osc[t]=cum[t]-ma
# scostamento alto -> EURUSD scende nei prossimi H giorni? (reversione = corr negativa)
for H in (5,10,20):
    idx={D[i]:D[i+H] for i in range(len(D)-H)}
    seq=[t for t in osc if t in idx]
    report(f"osc EUR-spec_t -> EURUSD ret {H}g (rev=neg)", seq, lambda t:osc[t], lambda t:(EUR[idx[t]]-EUR[t])*10000)
    report(f"osc EUR-spec_t -> EUR-spec ret {H}g (rev=neg)", seq, lambda t:osc[t], lambda t:cum[idx[t]]-cum[t])
