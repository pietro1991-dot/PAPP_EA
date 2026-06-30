#!/usr/bin/env python3
"""
line_cross_validate.py - Rigore sui candidati LINEA-LINEA (file nuovo, non tocca nulla).
1) TEST DEL NULLA a permutazione: l'edge del pattern batte N entrate CASUALI con la
   stessa direzione/SL/TP? (Cruciale: il profilo TP-stretto/SL-MA365 fa soldi anche a
   caso per geometria; il pattern vale solo se batte il caso = il TIMING del cross conta.)
2) SOVRAPPOSIZIONE coi 6 pattern prezzo-linea esistenti e tra candidati (per data, ±K barre):
   se i trade coincidono, è lo stesso edge, non ne aggiunge di nuovo.
"""
import random
from statistics import mean
import pattern_mining as pm
import line_cross_mining as lcm

random.seed(12345)
CSV="../EURUSD/PAPP_Export.csv"; SPREAD=15; M=300; K=3
rows=pm.load_csv(CSV)
base28=lcm.build_all28_entries(rows)

# candidati credibili dal Livello 1 (tag, is_fade, dir_finale, SL, TP)
CANDS=[
  ("XMA30_MA7", False, +1, "MA365", 15),
  ("XMA30_MA3", False, -1, "MA365", 15),
  ("XMA14_MA3", True,  -1, "MA365", 12),
  ("XMA7_Median",False,+1, "MA365", 15),
  ("XMA14_MA7", True,  +1, "MA365", 12),
]
# 6 pattern prezzo-linea esistenti (line, dir)
EXIST=[("MA30",-1),("MA121",+1),("MA365",-1),("MA7",-1),("MA30",+1),("MA14",+1)]

def recon(tag,is_fade,fdir):
    es=[e for e in base28 if e['line']==tag]
    if is_fade: es=[{**e,'dir':-e['dir']} for e in es]
    return [e for e in es if e['dir']==fdir]

def sl_ok(idx,buy,sl_col):
    try: sv=float(rows[idx][sl_col]); pr=float(rows[idx]['close'])
    except: return False
    if not (0<sv<1e12): return False
    return (sv<pr) if buy else (sv>pr)   # SL dal lato giusto (come analyze_dynamic_sl_grid)

def sim(idx,buy,sl_col,tp):
    if not sl_ok(idx,buy,sl_col): return None
    o=pm.simulate_trade(rows,idx,buy,float(rows[idx]['close']),sl_col,tp,SPREAD)
    return None if o is None else o[0]

def valid_idxs(buy,sl_col):
    out=[]
    for i in range(len(rows)-2):
        try: sv=float(rows[i][sl_col]); pr=float(rows[i]['close'])
        except: continue
        if not (0<sv<1e12): continue
        if (buy and sv>=pr) or ((not buy) and sv<=pr): continue
        out.append(i)
    return out

# entries prezzo-linea esistenti (per overlap)
pl=pm.detect_entries(rows, include_line_cross=False)
exist_idx=set()
for (ln,dr) in EXIST:
    for e in pl:
        if e['line']==ln and e['dir']==dr: exist_idx.add(e['idx'])

print("=== VALIDAZIONE candidati LINEA-LINEA (null test + overlap) ===\n")
cand_idxsets=[]
for tag,fade,fdir,sl,tp in CANDS:
    sl_col=pm.LINE_COLS[pm.LINE_NAMES.index(sl)]; buy=(fdir==1)
    es=recon(tag,fade,fdir)
    pnls=[]; idxs=[]
    for e in es:
        p=sim(e['idx'],buy,sl_col,tp)
        if p is not None: pnls.append(p); idxs.append(e['idx'])
    if len(pnls)<10: print(f"{tag}: pochi trade"); continue
    actual=sum(pnls); n=len(pnls)
    # NULL: n entrate casuali, stessa dir/SL/TP
    pool=valid_idxs(buy,sl_col); nulls=[]
    for _ in range(M):
        pick=random.sample(pool,min(n,len(pool)))
        tot=0.0
        for i in pick:
            p=sim(i,buy,sl_col,tp)
            if p is not None: tot+=p
        nulls.append(tot)
    nulls.sort(); above=sum(1 for x in nulls if x>=actual); pval=above/M
    null_med=nulls[len(nulls)//2]
    # OVERLAP coi 6 esistenti (entrata entro ±K barre)
    ov=sum(1 for ix in idxs if any((ix-K)<=ex<=(ix+K) for ex in exist_idx))/n*100
    cand_idxsets.append((tag,fdir,set(idxs)))
    flag = "EDGE VERO (batte il caso)" if pval<0.05 else ("dubbio" if pval<0.15 else "= AL CASO (no edge timing)")
    print(f"{('F:' if fade else '')+tag:14s} {'BUY' if buy else 'SELL':4s} SL={sl} TP={tp}: N={n} tot={actual:+.0f}")
    print(f"   NULL: mediana caso={null_med:+.0f}  p-value={pval:.3f}  -> {flag}")
    print(f"   OVERLAP coi 6 esistenti (±{K} barre): {ov:.0f}%\n")

# overlap tra candidati
print("=== sovrapposizione TRA candidati (% entrate condivise ±0 barre) ===")
for i in range(len(cand_idxsets)):
    for j in range(i+1,len(cand_idxsets)):
        a=cand_idxsets[i][2]; b=cand_idxsets[j][2]
        if a and b:
            ov=len(a&b)/min(len(a),len(b))*100
            if ov>20: print(f"  {cand_idxsets[i][0]} ~ {cand_idxsets[j][0]}: {ov:.0f}% condiviso")
print("(coppie sotto 20% non mostrate = indipendenti)")
