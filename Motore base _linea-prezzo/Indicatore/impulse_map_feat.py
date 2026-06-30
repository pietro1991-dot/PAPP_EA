#!/usr/bin/env python3
"""
impulse_map_feat.py - INTERAZIONI cross x feature (file nuovo). La risposta all'impulso
NUDA e' piatta; qui cerco se DENTRO un regime-feature il cross predice la direzione.
Per ogni cross x orizzonte x feature, split alla mediana (low/high), misuro E[fwd·dir]
in ogni meta', train(<2020)/test. Pattern = una meta' con segno concorde train+test e
|t|>2 su entrambi. Riporto i sopravvissuti e il conteggio vs il caso (multiple testing).
Dati: EURUSD D1.
"""
from statistics import mean, pstdev
import pattern_mining as pm
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows); PT=pm.PT_SIZE
SPLIT="2020.01.01"
def gf(i,c):
    try: return float(rows[i][c])
    except: return None
close=[gf(i,'close') for i in range(n)]; dts=[rows[i]['datetime'] for i in range(n)]
LINES=pm.LINE_COLS; NAMES=pm.LINE_NAMES
H=[5,20,60]; FEATS=['cluPct','velPct','accPct','volPct']
FWD={h:[ (close[i+h]-close[i])/PT if (i+h<n and close[i] and close[i+h]) else None for i in range(n)] for h in H}
def crosses(ca,cb):
    ev=[]; prev=None
    for i in range(n):
        va,vb=gf(i,ca),gf(i,cb)
        if not (va and vb and 0<va<1e12 and 0<vb<1e12): prev=None; continue
        s=1 if va>vb else 0
        if prev is not None and s!=prev: ev.append((i,1 if (prev==0 and s==1) else -1))
        prev=s
    return ev
def tt(xs):
    xs=[x for x in xs if x is not None]
    if len(xs)<8: return 0,0,0
    m=mean(xs); sd=pstdev(xs); return m,(m/(sd/len(xs)**0.5) if sd>0 else 0),len(xs)
hits=[]; ntests=0
for a in range(len(LINES)):
    for b in range(a+1,len(LINES)):
        ev=crosses(LINES[a],LINES[b])
        if len(ev)<30: continue
        tag=f"{NAMES[a]}x{NAMES[b]}"
        for feat in FEATS:
            fv=[(i,d,gf(i,feat)) for (i,d) in ev if gf(i,feat) is not None]
            if len(fv)<30: continue
            trvals=[x[2] for x in fv if dts[x[0]]<SPLIT]
            if len(trvals)<15: continue
            med=sorted(trvals)[len(trvals)//2]
            for half,lab in ((0,'low'),(1,'high')):
                sel=[(i,d) for (i,d,v) in fv if (v<=med if half==0 else v>med)]
                for h in H:
                    ntests+=1
                    tr=[FWD[h][i]*d for (i,d) in sel if dts[i]<SPLIT and FWD[h][i] is not None]
                    te=[FWD[h][i]*d for (i,d) in sel if dts[i]>=SPLIT and FWD[h][i] is not None]
                    mtr,ttr,ntr=tt(tr); mte,tte,nte=tt(te)
                    if ntr>=12 and nte>=8 and mtr*mte>0 and abs(ttr)>=2 and abs(tte)>=2:
                        hits.append((tag,feat,lab,h,mtr,ttr,mte,tte,ntr+nte))
hits.sort(key=lambda x:-min(abs(x[5]),abs(x[7])))
print(f"=== INTERAZIONI cross x feature (EURUSD D1) | {ntests} test ===")
print(f"{'cross':12s} {'feat':7s} {'lato':4s} {'h':>3s} | TRAIN m/t | TEST m/t | N")
for tag,feat,lab,h,mtr,ttr,mte,tte,N in hits:
    print(f"  {tag:11s} {feat:7s} {lab:4s} {h:>3d} | {mtr:+5.0f}/{ttr:+4.1f} | {mte:+5.0f}/{tte:+4.1f} | {N}")
print(f"\n  sopravvissuti: {len(hits)} | attesi PER CASO (~5% di {ntests} con |t|>2 su 2 campioni indip ~0.2%%): ~{ntests*0.002:.0f}")
print("  -> se sopravvissuti >> attesi-per-caso, c'e' segnale reale nelle interazioni.")
