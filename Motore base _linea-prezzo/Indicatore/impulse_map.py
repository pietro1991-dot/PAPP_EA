#!/usr/bin/env python3
"""
impulse_map.py - MAPPA DI RISPOSTA ALL'IMPULSO dei cross linea-linea (file nuovo).
Segnale PURO, esente da uscita: per ogni cross misura E[rendimento futuro a h barre
NELLA direzione del cross] a molti orizzonti, vs NULL "stessa direzione a caso"
(isola il TIMING dal drift). Train(<2020)/Test. Trova DOVE c'e' predittivita' reale:
positivo = il cross predice CONTINUAZIONE; negativo = INVERSIONE.
Dati: EURUSD D1.
"""
import random
from statistics import mean, pstdev
import pattern_mining as pm
random.seed(3)
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows); PT=pm.PT_SIZE
SPLIT="2020.01.01"
def gf(i,c):
    try: return float(rows[i][c])
    except: return None
close=[gf(i,'close') for i in range(n)]
dts=[rows[i]['datetime'] for i in range(n)]
LINES=pm.LINE_COLS; NAMES=pm.LINE_NAMES
H=[3,5,10,20,40,60,120]
# rendimenti futuri (punti) precompilati
FWD={h:[None]*n for h in H}
for h in H:
    for i in range(n-h):
        if close[i] and close[i+h]: FWD[h][i]=(close[i+h]-close[i])/PT
def crosses(ca,cb):
    ev=[]; prev=None
    for i in range(n):
        va,vb=gf(i,ca),gf(i,cb)
        if not (va and vb and 0<va<1e12 and 0<vb<1e12): prev=None; continue
        s=1 if va>vb else 0
        if prev is not None and s!=prev: ev.append((i, 1 if (prev==0 and s==1) else -1))
        prev=s
    return ev
allbars=[i for i in range(n) if close[i] is not None]
def tstat(xs):
    xs=[x for x in xs if x is not None]
    if len(xs)<8: return 0.0,0.0,0
    m=mean(xs); sd=pstdev(xs)
    return m, (m/(sd/ (len(xs)**0.5)) if sd>0 else 0.0), len(xs)

print("=== MAPPA RISPOSTA ALL'IMPULSO | EURUSD D1 | E[fwd · dir cross], pt ===")
print("  + = continuazione, - = inversione. Cerco: stesso segno TRAIN+TEST e |t|>2 su entrambi, batte null.")
hits=[]
for a in range(len(LINES)):
    for b in range(a+1,len(LINES)):
        ev=crosses(LINES[a],LINES[b])
        if len(ev)<20: continue
        tag=f"{NAMES[a]}x{NAMES[b]}"
        for h in H:
            tr=[FWD[h][i]*d for (i,d) in ev if dts[i]<SPLIT and FWD[h][i] is not None]
            te=[FWD[h][i]*d for (i,d) in ev if dts[i]>=SPLIT and FWD[h][i] is not None]
            mtr,ttr,ntr=tstat(tr); mte,tte,nte=tstat(te)
            if ntr<10 or nte<8: continue
            # robusto: stesso segno train+test, |t|>=2 su entrambi
            if (mtr*mte>0) and abs(ttr)>=2 and abs(tte)>=2:
                # null: stessa direzione-mix a caso (isola timing)
                dirs=[d for (i,d) in ev]; M=200; nn=0
                actual=mean([FWD[h][i]*d for (i,d) in ev if FWD[h][i] is not None])
                for _ in range(M):
                    picks=random.sample(allbars,len(dirs))
                    vals=[FWD[h][j]*d for j,d in zip(picks,dirs) if FWD[h][j] is not None]
                    if mean(vals)*(1 if actual>0 else -1) >= actual*(1 if actual>0 else -1): nn+=1
                p=nn/M
                hits.append((tag,h,mtr,ttr,mte,tte,ntr+nte,p))
hits.sort(key=lambda x:-abs(x[2]+x[4]))
print(f"\n{'cross':14s} {'h':>4s} | {'TRAIN m/t':>13s} | {'TEST m/t':>13s} | N | null p | tipo")
for tag,h,mtr,ttr,mte,tte,N,p in hits:
    tipo = ("CONTINUA" if mtr>0 else "INVERTE")
    star=" <==" if p<0.05 else ""
    print(f"  {tag:12s} {h:>4d} | {mtr:+6.0f}/{ttr:+4.1f} | {mte:+6.0f}/{tte:+4.1f} | {N:3d} | {p:.3f} | {tipo}{star}")
print(f"\n  pattern robusti (segno concorde + |t|>2 train&test): {len(hits)} | di cui battono il null: {sum(1 for x in hits if x[7]<0.05)}")
