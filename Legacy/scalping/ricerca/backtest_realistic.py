#!/usr/bin/env python3
"""
backtest_realistic.py - la reversione con esecuzione REALISTICA vs idealizzata.
Realismi:
  1) entri/esci alla barra SUCCESSIVA (open[j+1]), non al close del segnale (delay).
  2) spread NON fisso: base + k*ATR -> si allarga sugli spike (la reversione entra
     proprio dopo i movimenti forti = spread largo).
Confronto: ideale (close, costo 12) vs realistico.

Uso: python3 backtest_realistic.py [../data/scalp_EURUSD_h1.csv] [--split=2020.01.01]
"""
import sys, numpy as np
from numpy.lib.stride_tricks import sliding_window_view

PATH="../data/scalp_EURUSD_h1.csv"; SPLIT="2020.01.01"; PT=1e-5
W=300; LO=5.0; HI=95.0; MAXHOLD=48
for a in sys.argv[1:]:
    if a.startswith("--split="): SPLIT=a.split("=")[1]
    elif not a.startswith("--"): PATH=a

hdr=open(PATH).readline().strip().split(","); ix={h:i for i,h in enumerate(hdr)}
r=np.genfromtxt(PATH,delimiter=",",skip_header=1,usecols=[ix["open"],ix["close"],ix["dMed"],ix["atr"]],dtype=float)
yrs=np.genfromtxt(PATH,delimiter=",",skip_header=1,usecols=[0],dtype="U4").astype(int)
opn,close,dmed,atr=r[:,0],r[:,1],r[:,2],r[:,3]
atr=np.where(np.isfinite(atr),atr,150.0)   # ripulisci gli inf iniziali
n=len(close); split_i=int(np.argmax(yrs>=int(SPLIT[:4])))
osc=np.full(n,np.nan); win=sliding_window_view(dmed,W); osc[W-1:]=(win<=dmed[W-1:][:,None]).mean(1)*100

def summ(tr):
    ptr=np.array([x[1] for x in tr if x[0]<split_i]); pte=np.array([x[1] for x in tr if x[0]>=split_i])
    def m(p):
        if len(p)<5: return (0,0,0,len(p))
        w=p[p>0]; l=p[p<0]; pf=w.sum()/abs(l.sum()) if l.sum() else 9.9
        return p.sum(),pf,p.mean(),len(p)
    a=m(ptr); b=m(pte)
    return a,b

def run(mode, base=10.0, k=0.15):
    """mode 'ideal' o 'real'."""
    pos=0;entry=0;ej=0;dirn=0;tr=[]
    for j in range(W,n-1):
        o=osc[j]
        if o!=o: continue
        if pos==0:
            d=1 if o<LO else (-1 if o>HI else 0)
            if d!=0:
                pos,dirn,ej=1,d,j
                if mode=="ideal": entry=close[j]; entry_cost=0
                else: entry=opn[j+1]; entry_cost=(base+k*atr[j])  # spread pieno round-trip qui
        else:
            ex=(dirn==1 and o>=50) or (dirn==-1 and o<=50) or (j-ej)>=MAXHOLD
            if ex:
                if mode=="ideal":
                    pnl=dirn*(close[j]-entry)/PT-12.0
                else:
                    exitpx=opn[j+1]
                    pnl=dirn*(exitpx-entry)/PT-entry_cost
                tr.append((ej,pnl)); pos=0
    return tr

print(f"File:{PATH} n={n} | split {SPLIT[:4]}\n")
print(f"{'scenario':34} | {'net TRAIN':>10} {'PF':>4} {'avg':>6} {'N':>5} | {'net TEST':>10} {'PF':>4} {'avg':>6} {'N':>5}")
print("-"*104)
def show(lbl,tr):
    a,b=summ(tr)
    print(f"{lbl:34} | {a[0]:>10.0f} {a[1]:>4.2f} {a[2]:>6.1f} {a[3]:>5} | {b[0]:>10.0f} {b[1]:>4.2f} {b[2]:>6.1f} {b[3]:>5}")
show("IDEALE (close, costo 12)", run("ideal"))
show("REALE base=10 k=0.15 (spread~ATR)", run("real",10,0.15))
show("REALE base=15 k=0.20", run("real",15,0.20))
show("REALE base=15 k=0.30 (pessimista)", run("real",15,0.30))
print("\navg = punti medi per trade. Confronta con l'EA nel tester (~0.6 pip = 6 punti/trade).")
print("ATR medio (punti):", f"{np.nanmean(atr):.0f}", "| ATR sui bar d'entrata estrema conta (spread ~ base + k*ATR).")
