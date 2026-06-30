#!/usr/bin/env python3
"""
line_feat_deploy.py - Seleziona pattern LINEA-LINEA + filtro VELOCITA' CONCORDE deployabili.
File nuovo, non tocca i 6 pattern prezzo-linea esistenti.
1) Tutti i 28 cross, filtrati a vel_agree=1 (segno vel% == direzione del cross).
2) Griglia SL x TP (riusa analyze_dynamic_sl_grid). Train/test split.
3) Tiene i robusti: N>=MINN, train+test positivi, PF>1.3 entrambi.
4) Per i sopravvissuti: NULL CONDIZIONATO (entrate casuali con vel_agree=1, stessa dir/SL/TP).
   Deployabile = robusto E batte il null (p<0.05) E EV decente.
"""
import random
from statistics import mean
from collections import defaultdict
import pattern_mining as pm
import line_cross_mining as lcm
random.seed(99)
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows)
SPREAD=15; SPLIT="2020.01.01"; MINN=30
def vsgn(i):
    try:
        v=float(rows[i]['vel%']); return 1 if v>0 else (-1 if v<0 else 0)
    except: return 0

base=lcm.build_all28_entries(rows)
# filtro vel_agree=1
ent=[e for e in base if vsgn(e['idx'])==e['dir']]
print(f"cross totali {len(base)} -> con velocita' concorde {len(ent)}")
res=pm.analyze_dynamic_sl_grid(ent, rows, spread_pt=SPREAD)
pats=defaultdict(lambda:{'tr':[],'te':[],'idx':[]})
for r in res:
    k=(r['line'],r['dir'],r['sl_line'],r['tp_pt'])
    b='tr' if r['datetime']<SPLIT else 'te'
    pats[k][b].append(r['pnl_pt']); pats[k]['idx'].append((r['idx'],r['dir']))
def stt(p):
    if not p: return (0,0,0,0)
    n_=len(p); tot=sum(p); g=sum(x for x in p if x>0); l=-sum(x for x in p if x<0)
    return (n_,tot,(g/l if l>0 else 9.99),sum(1 for x in p if x>0)/n_*100)
# robusti
cand=[]
for k,d in pats.items():
    ntr,ttr,pftr,wtr=stt(d['tr']); nte,tte,pfte,wte=stt(d['te'])
    N=ntr+nte
    if N>=MINN and ntr>=12 and nte>=8 and ttr>0 and tte>0 and pftr>1.3 and pfte>1.3:
        cand.append((k,N,ttr,pftr,wtr,ntr,tte,pfte,wte,nte,(ttr+tte)/N,d['idx']))
cand.sort(key=lambda x:-x[10])   # per EV
def sl_ok(i,buy,sl_col):
    try: sv=float(rows[i][sl_col]); pr=float(rows[i]['close'])
    except: return False
    return 0<sv<1e12 and ((sv<pr) if buy else (sv>pr))
def cond_null(idx_dirs,sl_col,tp,M=200):
    act=0
    for (i,d) in idx_dirs:
        o=pm.simulate_trade(rows,i,d==1,float(rows[i]['close']),sl_col,tp,SPREAD)
        if o: act+=o[0]
    # pool: bar con velocita' concorde E SL dal lato giusto per quella direzione (come l'attuale)
    pool=[i for i in range(2,n-2) if vsgn(i)!=0 and sl_ok(i, vsgn(i)==1, sl_col)]
    N=len(idx_dirs); nulls=[]
    for _ in range(M):
        picks=random.sample(pool,min(N,len(pool))); tot=0
        for i in picks:
            d=vsgn(i)
            o=pm.simulate_trade(rows,i,d==1,float(rows[i]['close']),sl_col,tp,SPREAD)
            if o: tot+=o[0]
        nulls.append(tot)
    nulls.sort(); return act, nulls[M//2], sum(1 for x in nulls if x>=act)/M

print(f"\n=== PATTERN ROBUSTI (vel_agree, N>={MINN}, train+test PF>1.3) — con NULL condizionato ===")
print(f"{'pattern':28s} | {'TRAIN N/tot/PF':16s} | {'TEST N/tot/PF':16s} | EV | null p")
depl=[]
for c in cand[:20]:
    (ln,dr,sl,tp),N,ttr,pftr,wtr,ntr,tte,pfte,wte,nte,ev,idxs=c
    sl_col=pm.LINE_COLS[pm.LINE_NAMES.index(sl)]
    act,med,p=cond_null(idxs,sl_col,tp)
    d='BUY' if dr==1 else 'SELL'
    star=' <== DEPLOY' if (p<0.05 and ev>50) else ''
    print(f"  {ln:12s}{d:4s}SL={sl:6s}TP{tp:2d} | N{ntr:3d}{ttr:+6.0f} PF{pftr:.1f} | N{nte:3d}{tte:+6.0f} PF{pfte:.1f} | {ev:+4.0f} | p={p:.3f}{star}")
    if p<0.05 and ev>50: depl.append(c)
print(f"\n  candidati robusti: {len(cand)} | deployabili (battono null p<0.05 & EV>50pt=5pip): {len(depl)}")
