#!/usr/bin/env python3
"""
pooled_slow_cross.py - Segnale "INVERSIONE STRUTTURALE" (file nuovo, non tocca nulla).
Insieme di PRINCIPIO (no cherry-pick): tutte le C(4,2)=6 coppie tra le 4 linee LENTE
(MA30, MA121, MA182, MA365). Entry nella direzione del cross (trend-following dell'inversione).
USCITA DI TREND: il prezzo ri-attraversa MA30 contro la posizione, OPPURE stop dinamico su
MA365, OPPURE max-hold. Una posizione per volta. Validazione train/test + test del nulla.
Dati: export EURUSD D1.
"""
import random
from statistics import mean
import pattern_mining as pm
random.seed(7)
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows); PT=pm.PT_SIZE
SPREAD=15; SPLIT="2020.01.01"; HOLDMAX=200
def g(i,c):
    try: return float(rows[i][c])
    except: return None
SLOW=['MA30','MA121','MA182','MA365']

def events():
    ev=[]
    for a in range(len(SLOW)):
        for b in range(a+1,len(SLOW)):
            ca,cb=SLOW[a],SLOW[b]; prev=None
            for i in range(n):
                va,vb=g(i,ca),g(i,cb)
                if not (va and vb and 0<va<1e12 and 0<vb<1e12): prev=None; continue
                s=1 if va>vb else 0
                if prev is not None and s!=prev:
                    ev.append((i, 1 if (prev==0 and s==1) else -1, f"{ca}x{cb}"))
                prev=s
    ev.sort(); return ev

def exit_trade(i,d):
    """entra a close[i] in direzione d; esce su: prezzo ri-attraversa MA30 contro,
    stop su MA365, o max-hold. Ritorna (pnl_pt, exit_idx, motivo)."""
    entry=g(i,'close')
    for j in range(i+1,min(i+HOLDMAX,n)):
        hi=g(j,'high'); lo=g(j,'low'); cl=g(j,'close')
        sl=g(j-1,'MA365'); m30=g(j,'MA30')
        if None in (hi,lo,cl,sl,m30): continue
        # stop strutturale su MA365
        if d>0 and lo<=sl: return (sl-entry)/PT - SPREAD, j, 'SL'
        if d<0 and hi>=sl: return (entry-sl)/PT - SPREAD, j, 'SL'
        # uscita di trend: il prezzo torna oltre MA30 contro la posizione
        if d>0 and cl<m30: return (cl-entry)/PT - SPREAD, j, 'MA30'
        if d<0 and cl>m30: return (entry-cl)/PT - SPREAD, j, 'MA30'
    j=min(i+HOLDMAX,n-1); cl=g(j,'close')
    return ((cl-entry)/PT*d - SPREAD, j, 'HOLD') if cl else (None,j,'NA')

def run(ev):
    trades=[]; i_block=-1
    for (i,d,name) in ev:
        if i<=i_block: continue            # una posizione per volta
        r=exit_trade(i,d)
        if r[0] is None: continue
        trades.append({'idx':i,'dir':d,'name':name,'pnl':r[0],'exit':r[1]})
        i_block=r[1]
    return trades

def stats(ts):
    if len(ts)<5: return None
    p=[t['pnl'] for t in ts]; tot=sum(p); win=sum(1 for x in p if x>0)/len(p)*100
    gp=sum(x for x in p if x>0); gl=-sum(x for x in p if x<0); pf=gp/gl if gl>0 else 9.99
    eq=[]; c=0
    for x in p: c+=x; eq.append(c)
    peak=eq[0]; dd=0
    for v in eq:
        peak=max(peak,v); dd=min(dd,v-peak)
    return dict(N=len(p),tot=tot,win=win,pf=pf,rdd=(tot/-dd if dd<0 else 9.9),ev=tot/len(p))

ev=events()
tr=run(ev)
print(f"=== INVERSIONE STRUTTURALE (6 coppie lente, pool onesto) | {len(ev)} eventi -> {len(tr)} trade non sovrapposti ===")
alls=stats(tr)
trn=[t for t in tr if rows[t['idx']]['datetime']<SPLIT]; tst=[t for t in tr if rows[t['idx']]['datetime']>=SPLIT]
for lbl,s in [("TUTTO",alls),("TRAIN<2020",stats(trn)),("TEST>=2020",stats(tst))]:
    if s: print(f"  {lbl:11s}: N={s['N']:3d} tot={s['tot']:+7.0f}pt EV={s['ev']:+5.0f} win={s['win']:3.0f}% PF={s['pf']:.2f} R/DD={s['rdd']:.1f}")
# contributo per coppia (trasparenza: i 'losers' aiutano o no?)
print("\n  contributo per coppia:")
from collections import defaultdict
byp=defaultdict(list)
for t in tr: byp[t['name']].append(t['pnl'])
for name,p in sorted(byp.items(),key=lambda kv:-sum(kv[1])):
    print(f"    {name:14s}: N={len(p):3d} tot={sum(p):+7.0f} win={sum(1 for x in p if x>0)/len(p)*100:3.0f}%")
# NULL: stesse N entrate casuali, stessa direzione, stessa uscita
print("\n  test del nulla (entrate casuali, stessa direzione/uscita):")
dirs=[t['dir'] for t in tr]; M=300; pool=[i for i in range(2,n-HOLDMAX)]
nulls=[]
for _ in range(M):
    picks=random.sample(pool,len(dirs)); tot=0; ok=0
    for i,d in zip(picks,dirs):
        r=exit_trade(i,d)
        if r[0] is not None: tot+=r[0]; ok+=1
    nulls.append(tot)
nulls.sort(); above=sum(1 for x in nulls if x>=alls['tot'])
print(f"    reale tot={alls['tot']:+.0f} | mediana caso={nulls[M//2]:+.0f} | p-value={above/M:.3f} -> {'EDGE VERO' if above/M<0.05 else 'dubbio/al caso'}")
