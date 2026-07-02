#!/usr/bin/env python3
"""
probe_regime.py - REVERT vs TREND dallo stesso oscillatore.
Definizione:
  d   = close - Median ; osc = percentile di d su W ; osc in [0,100] (SATURA).
  L'info trend/revert non e' nell'osc (si appiattisce) ma nella ROTTURA della
  distanza grezza: d fa un NUOVO estremo su M barre => BREAKOUT/TREND ; altrimenti
  l'estremo si "stanca" => REVERSIONE.

Test:
  (baseline) reversione cieca: osc<Lo BUY / osc>Hi SELL, esci a 50/MaxHold.
  (H1) reversione FILTRATA: fada solo se NON sta rompendo (estremo che si stanca).
  (H2) trend-follow: sulla rottura fresca, segui -> ha follow-through oltre il costo?

Uso: python3 probe_regime.py [../data/scalp_EURUSD_h1.csv] [--cost=12] [--split=2020.01.01] [--M=24]
"""
import sys, numpy as np
from numpy.lib.stride_tricks import sliding_window_view

PATH="../data/scalp_EURUSD_h1.csv"; COST=12.0; SPLIT="2020.01.01"; PT=1e-5
W=300; LO=5.0; HI=95.0; MAXHOLD=48; M=24
for a in sys.argv[1:]:
    if a.startswith("--cost="): COST=float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT=a.split("=")[1]
    elif a.startswith("--M="): M=int(a.split("=")[1])
    elif not a.startswith("--"): PATH=a

hdr=open(PATH).readline().strip().split(","); ix={h:i for i,h in enumerate(hdr)}
r=np.genfromtxt(PATH,delimiter=",",skip_header=1,usecols=[ix["close"],ix["dMed"]],dtype=float)
yrs=np.genfromtxt(PATH,delimiter=",",skip_header=1,usecols=[0],dtype="U4").astype(int)
close,dmed=r[:,0],r[:,1]; n=len(close); split_i=int(np.argmax(yrs>=int(SPLIT[:4])))

osc=np.full(n,np.nan)
win=sliding_window_view(dmed,W); osc[W-1:]=(win<=dmed[W-1:][:,None]).mean(1)*100

# breakout: d fa un nuovo estremo sulle M barre PRECEDENTI
brk_up=np.zeros(n,bool); brk_dn=np.zeros(n,bool)
wm=sliding_window_view(dmed,M)            # finestre [i:i+M]
for j in range(M,n):
    prev=wm[j-M]                          # d[j-M:j]
    brk_up[j]=dmed[j]>prev.max()
    brk_dn[j]=dmed[j]<prev.min()

def stats(p):
    if len(p)<2: return 0.0,0.0
    m=p.mean(); sd=p.std(ddof=1); return m,(m/(sd/np.sqrt(len(p))) if sd>0 else 0)

def bt(entry_ok):
    pos=0;entry=0;ej=0;dirn=0;tr=[]
    for j in range(W,n):
        o=osc[j]
        if o!=o: continue
        if pos==0:
            d=entry_ok(j)
            if d!=0: pos,dirn,entry,ej=1,d,close[j],j
        else:
            ex=(dirn==1 and o>=50) or (dirn==-1 and o<=50) or (j-ej)>=MAXHOLD
            if ex: tr.append((ej,dirn*(close[j]-entry)/PT-COST)); pos=0
    return tr

def report(name,tr):
    ptr=np.array([x[1] for x in tr if x[0]<split_i]); pte=np.array([x[1] for x in tr if x[0]>=split_i])
    if len(ptr)<10 or len(pte)<10: print(f"  {name:26} (pochi)"); return
    def m(p):
        w=p[p>0]; l=p[p<0]; pf=w.sum()/abs(l.sum()) if l.sum() else 9.9
        eq=np.cumsum(p); dd=(np.maximum.accumulate(eq)-eq).max()
        return p.sum(),pf,100*len(w)/len(p),dd
    a=m(ptr); b=m(pte)
    print(f"  {name:26} | TR net={a[0]:>8.0f} PF={a[1]:.2f} win={a[2]:.0f}% DD={a[3]:.0f} N={len(ptr)} | TE net={b[0]:>8.0f} PF={b[1]:.2f} win={b[2]:.0f}% DD={b[3]:.0f} N={len(pte)}")

print(f"File:{PATH} n={n} costo={COST} W={W} {LO}/{HI} MaxHold={MAXHOLD} M(breakout)={M} | split {SPLIT[:4]}\n")
print("REVERSIONE — baseline vs filtrata (salta gli estremi che SFONDANO):")
report("baseline (fade cieco)", bt(lambda j: 1 if osc[j]<LO else (-1 if osc[j]>HI else 0)))
report("FILTRATA (no breakout)", bt(lambda j: 1 if (osc[j]<LO and not brk_dn[j]) else (-1 if (osc[j]>HI and not brk_up[j]) else 0)))
report("SOLO breakout (fade)",   bt(lambda j: 1 if (osc[j]<LO and brk_dn[j]) else (-1 if (osc[j]>HI and brk_up[j]) else 0)))

print("\nTREND-FOLLOW — sulla rottura fresca, segui la direzione (return a h barre, netto costo):")
def follow(hz):
    tr,te=[],[]
    for j in range(M,n-max(hz)-1):
        d=1 if brk_up[j] else (-1 if brk_dn[j] else 0)
        if d==0: continue
        row=(tr if j<split_i else te)
        row.append(j*0+d)  # placeholder, calcolo sotto
    return
for h in [6,12,24,48]:
    tr,te=[],[]
    for j in range(M,n-h-1):
        d=1 if brk_up[j] else (-1 if brk_dn[j] else 0)
        if d==0: continue
        ret=d*(close[j+h]-close[j])/PT-COST
        (tr if j<split_i else te).append(ret)
    tr,te=np.array(tr),np.array(te)
    if len(tr)<20 or len(te)<20: continue
    mtr,ttr=stats(tr); mte,tte=stats(te)
    v="★★" if (mtr>0 and mte>0 and abs(ttr)>2 and abs(tte)>2) else ("★" if mtr>0 and mte>0 else "")
    print(f"  h={h:>2} | TR N={len(tr):>5} net={mtr:>7.1f} t={ttr:>5.1f} | TE N={len(te):>5} net={mte:>7.1f} t={tte:>5.1f} {v}")
