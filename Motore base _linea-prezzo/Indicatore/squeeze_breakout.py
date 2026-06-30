#!/usr/bin/env python3
"""
squeeze_breakout.py - VIA 1: la COMPRESSIONE delle MA predice ESPANSIONE di range?
E il breakout che ne segue e' tradabile? (file nuovo, non tocca nulla)
NON chiediamo al cross la direzione (dimostrato impredicibile) - la da' la ROTTURA.
Parte A: compressione(i)=(max-min delle 7 MA)/close -> percentile rolling; predice il range futuro?
Parte B: backtest breakout box dopo squeeze, con STOP/uscita-trend, train/test.
NULL DECISIVO: i breakout DOPO squeeze battono i breakout NORMALI (stessa meccanica)?
Dati: EURUSD D1.
"""
from statistics import mean, median
import pattern_mining as pm
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows); PT=pm.PT_SIZE
SPLIT="2020.01.01"; SPREAD=15
def gf(i,c):
    try: return float(rows[i][c])
    except: return None
MAS=['MA3','MA7','MA14','MA30','MA121','MA182','MA365']
hi=[gf(i,'high') for i in range(n)]; lo=[gf(i,'low') for i in range(n)]; cl=[gf(i,'close') for i in range(n)]
dts=[rows[i]['datetime'] for i in range(n)]
# compressione: ampiezza del ventaglio MA / prezzo
comp=[None]*n
for i in range(n):
    vs=[gf(i,m) for m in MAS]
    if all(v and 0<v<1e12 for v in vs) and cl[i]:
        comp[i]=(max(vs)-min(vs))/cl[i]
# percentile rolling (252) della compressione
WIN=252; cpct=[None]*n
for i in range(n):
    if comp[i] is None: continue
    hist=[comp[j] for j in range(max(0,i-WIN),i) if comp[j] is not None]
    if len(hist)<60: continue
    cpct[i]=sum(1 for x in hist if x<comp[i])/len(hist)
def fwd_range(i,h):
    js=[j for j in range(i+1,min(i+h+1,n)) if hi[j] and lo[j]]
    if not js: return None
    return (max(hi[j] for j in js)-min(lo[j] for j in js))/PT

# ===== PARTE A: compressione -> espansione? =====
print("=== PARTE A: la compressione predice il range futuro? (range futuro in pt, h=10) ===")
H=10
for lbl,dd in (("TRAIN",lambda d:d<SPLIT),("TEST",lambda d:d>=SPLIT)):
    bins={0:[],1:[],2:[],3:[],4:[]}
    for i in range(n):
        if cpct[i] is None or not dd(dts[i]): continue
        fr=fwd_range(i,H)
        if fr is None: continue
        b=min(4,int(cpct[i]*5)); bins[b].append(fr)
    out=" ".join(f"q{b}({'compr' if b==0 else 'largo' if b==4 else '..'})={mean(v):.0f}" for b,v in bins.items() if len(v)>=10)
    print(f"  {lbl}: {out}")
    print(f"        (q0=MA piu' compresse, q4=piu' larghe; se q0>=q4 lo squeeze->espansione c'e')")

# ===== PARTE B: backtest breakout box dopo squeeze =====
K=10        # barre della box
WAIT=12     # finestra per il breakout dopo lo squeeze
MAXH=40     # max hold del trade
def box(i):
    js=[j for j in range(max(0,i-K+1),i+1) if hi[j] and lo[j]]
    if len(js)<K: return None
    return max(hi[j] for j in js), min(lo[j] for j in js)
def run_breakout(is_squeeze):
    """is_squeeze: funzione(i)->bool che arma la box. Ritorna lista trade pnl(pt)."""
    trades=[]; i=K; block=-1
    while i<n-2:
        if i<=block or cpct[i] is None or not is_squeeze(i):
            i+=1; continue
        bx=box(i)
        if not bx: i+=1; continue
        bh,bl=bx; entered=False
        for j in range(i+1,min(i+WAIT+1,n)):
            if hi[j] is None: continue
            buy=hi[j]>=bh; sell=lo[j]<=bl
            if buy or sell:
                d=1 if (buy and not sell) else (-1 if (sell and not buy) else (1 if cl[j]>=cl[j-1] else -1))
                entry=bh if d==1 else bl; stop=bl if d==1 else bh
                # gestione: stop opposto, uscita trend (close ri-attraversa MA30), max hold
                pnl=None
                for k in range(j,min(j+MAXH,n)):
                    if hi[k] is None: continue
                    if d==1 and lo[k]<=stop: pnl=(stop-entry)/PT-SPREAD; end=k; break
                    if d==-1 and hi[k]>=stop: pnl=(entry-stop)/PT-SPREAD; end=k; break
                    m30=gf(k,'MA30')
                    if m30:
                        if d==1 and cl[k]<m30: pnl=(cl[k]-entry)/PT-SPREAD; end=k; break
                        if d==-1 and cl[k]>m30: pnl=(entry-cl[k])/PT-SPREAD; end=k; break
                else:
                    end=min(j+MAXH,n-1); pnl=(cl[end]-entry)/PT*d-SPREAD
                if pnl is None: end=min(j+MAXH,n-1); pnl=(cl[end]-entry)/PT*d-SPREAD
                trades.append((i,pnl)); block=end; entered=True; i=end; break
        if not entered: i+=1
    return trades
def stats(ts):
    if len(ts)<5: return None
    p=[x[1] for x in ts]; tot=sum(p); g=sum(x for x in p if x>0); l=-sum(x for x in p if x<0)
    return len(p),tot,tot/len(p),(g/l if l>0 else 9.9),sum(1 for x in p if x>0)/len(p)*100
print("\n=== PARTE B: backtest breakout box ===")
for lbl,sig in (("SQUEEZE (comp_pct<0.2)", lambda i:cpct[i]<0.2),
                ("NORMALE (0.4<=comp_pct<0.6) [null]", lambda i:0.4<=cpct[i]<0.6)):
    ts=run_breakout(sig)
    tr=[t for t in ts if dts[t[0]]<SPLIT]; te=[t for t in ts if dts[t[0]]>=SPLIT]
    print(f"\n  {lbl}")
    for sl,s in (("TUTTO",stats(ts)),("TRAIN",stats(tr)),("TEST",stats(te))):
        if s: print(f"    {sl:6s} N={s[0]:3d} tot={s[1]:+6.0f} EV={s[2]:+5.0f} PF={s[3]:.2f} win={s[4]:3.0f}%")
