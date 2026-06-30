#!/usr/bin/env python3
"""
line_feat_combo.py - LINEA-LINEA x FEATURES (file nuovo, non tocca nulla).
Domanda: una feature (contesto) separa i cross BUONI dai cattivi? Cioe' aggiunge
informazione INDIPENDENTE, o e' ridondante (stesso prezzo)?

Metodo non superficiale:
- Pool di TUTTI i 28 cross linea-linea (con direzione + features all'entrata).
- Due metriche per ogni cross: (1) rendimento futuro +20 barre nella direzione del cross
  (pulito, niente geometria), (2) PnL scalp TP15/SL=MA365 (profilo tradabile).
- Condiziono su ogni feature con split alla MEDIANA (low/high), separatamente TRAIN(<2020)/TEST.
- Per i regimi promettenti: NULL CONDIZIONATO (entrate casuali NELLO STESSO regime, stessa dir).
- Consapevolezza multiple-testing: ~7 feature x 2 lati = 14 test, serve evidenza forte.
Dati: export EURUSD D1.
"""
import random
from statistics import mean, median
import pattern_mining as pm
random.seed(11)
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows); PT=pm.PT_SIZE
SPREAD=15; SPLIT="2020.01.01"; HFWD=20
def gf(i,c):
    try: return float(rows[i][c])
    except: return None
LINES=pm.LINE_COLS; NAMES=pm.LINE_NAMES
close=[gf(i,'close') for i in range(n)]

def all_line_cross():
    ev=[]
    for a in range(len(LINES)):
        for b in range(a+1,len(LINES)):
            ca,cb=LINES[a],LINES[b]; prev=None
            for i in range(n):
                va,vb=gf(i,ca),gf(i,cb)
                if not (va and vb and 0<va<1e12 and 0<vb<1e12): prev=None; continue
                s=1 if va>vb else 0
                if prev is not None and s!=prev:
                    ev.append((i, 1 if (prev==0 and s==1) else -1))
                prev=s
    return ev

def scalp_pnl(i,d):
    buy=(d==1); sl=gf(i,'MA365'); pr=close[i]
    if not (sl and pr and 0<sl<1e12 and ((sl<pr) if buy else (sl>pr))): return None
    o=pm.simulate_trade(rows,i,buy,pr,'MA365',15,SPREAD)
    return o[0] if o else None

def fwd(i,d):
    if i+HFWD>=n or close[i] is None or close[i+HFWD] is None: return None
    return (close[i+HFWD]-close[i])/PT*d

# costruisci dataset: per ogni cross -> features + metriche
F_NUM=['cluPct','velPct','accPct','volPct','orderScore']
ev=all_line_cross()
data=[]
for (i,d) in ev:
    row={'i':i,'d':d,'dt':rows[i]['datetime'],'scalp':scalp_pnl(i,d),'fwd':fwd(i,d)}
    for c in F_NUM:
        row[c]=gf(i,c)
    fr=gf(i,'spread')   # frattale (fast-slow)
    vsgn=gf(i,'vel%')
    row['frat_agree'] = 1 if (fr is not None and ((fr>0)==(d>0))) else 0      # frattale concorde col cross
    row['vel_agree']  = 1 if (vsgn is not None and ((vsgn>0)==(d>0))) else 0   # velocita' concorde
    data.append(row)
print(f"=== LINEA-LINEA x FEATURES | {len(data)} cross totali ===")
def st(rs,key):
    v=[r[key] for r in rs if r[key] is not None]
    if len(v)<8: return None
    tot=sum(v); win=sum(1 for x in v if x>0)/len(v)*100
    return (len(v),tot,tot/len(v),win)
def show(lbl,rs):
    s=st(rs,'scalp'); fwds=st(rs,'fwd')
    sc = f"scalp EV={s[2]:+5.0f} win{s[3]:3.0f}% N{s[0]}" if s else "scalp n/a"
    fw = f"fwd20 EV={fwds[2]:+5.0f} N{fwds[0]}" if fwds else "fwd n/a"
    print(f"   {lbl:22s} {sc} | {fw}")

tr=[r for r in data if r['dt']<SPLIT]; te=[r for r in data if r['dt']>=SPLIT]
print("\n-- BASELINE (tutti i cross, nessun filtro) --")
show("TRAIN", tr); show("TEST ", te)

print("\n-- CONDIZIONATO per FEATURE (split mediana train) --")
for feat in F_NUM+['frat_agree','vel_agree']:
    vals=[r[feat] for r in tr if r[feat] is not None]
    if not vals: continue
    if feat in ('frat_agree','vel_agree'):
        lo_tr=[r for r in tr if r[feat]==0]; hi_tr=[r for r in tr if r[feat]==1]
        lo_te=[r for r in te if r[feat]==0]; hi_te=[r for r in te if r[feat]==1]
        labels=('=0 (discorde)','=1 (concorde)')
    else:
        m=median(vals)
        lo_tr=[r for r in tr if r[feat] is not None and r[feat]<=m]; hi_tr=[r for r in tr if r[feat] is not None and r[feat]>m]
        lo_te=[r for r in te if r[feat] is not None and r[feat]<=m]; hi_te=[r for r in te if r[feat] is not None and r[feat]>m]
        labels=(f'<= {m:.2f}',f'> {m:.2f}')
    print(f"\n  [{feat}]")
    show(f"TRAIN {labels[0]}", lo_tr); show(f"TEST  {labels[0]}", lo_te)
    show(f"TRAIN {labels[1]}", hi_tr); show(f"TEST  {labels[1]}", hi_te)

# NULL CONDIZIONATO: per il regime piu' promettente sullo SCALP, batte il caso nello stesso regime?
def null_cond(subset_idx_dirs, M=300):
    # pool di tutte le barre valide; campiona casualmente N, stessa dir-mix, scalp
    dirs=[d for (_,d) in subset_idx_dirs]; N=len(dirs)
    if N<10: return None
    actual=sum(scalp_pnl(i,d) for (i,d) in subset_idx_dirs if scalp_pnl(i,d) is not None)
    pool=list(range(2,n-2)); nulls=[]
    for _ in range(M):
        picks=random.sample(pool,N); tot=0
        for i,d in zip(picks,dirs):
            p=scalp_pnl(i,d)
            if p is not None: tot+=p
        nulls.append(tot)
    nulls.sort(); above=sum(1 for x in nulls if x>=actual)
    return actual, nulls[M//2], above/M

print("\n-- NULL CORRETTO: il CROSS aggiunge valore, o basta 'entrare nel verso della velocita'?' --")
# bar dove la velocita' e' definita; per un'entrata casuale impongo dir=segno(vel%) -> vel_agree=1 per costruzione
velbars=[i for i in range(2,n-2) if gf(i,'vel%') is not None and gf(i,'vel%')!=0]
def dir_velagree(i): return 1 if gf(i,'vel%')>0 else -1
# ATTUALE: cross + vel_agree=1
sub=[(r['i'],r['d']) for r in data if r['vel_agree']==1 and scalp_pnl(r['i'],r['d']) is not None]
actual=sum(scalp_pnl(i,d) for (i,d) in sub); N=len(sub)
print(f"   ATTUALE cross+vel_agree=1: N={N} tot={actual:+.0f} EV={actual/N:+.0f}")
M=400; nulls=[]
for _ in range(M):
    picks=random.sample(velbars,min(N,len(velbars))); tot=0
    for i in picks:
        p=scalp_pnl(i,dir_velagree(i))   # entrata casuale MA con vel_agree=1 per costruzione
        if p is not None: tot+=p
    nulls.append(tot)
nulls.sort(); above=sum(1 for x in nulls if x>=actual)
print(f"   NULL (entrate casuali con vel_agree=1): mediana={nulls[M//2]:+.0f}  p-value={above/M:.3f}")
print(f"   -> {'IL CROSS aggiunge valore (interazione vera)' if above/M<0.05 else 'NO: basta entrare nel verso della velocita (il cross e ridondante)'}")
