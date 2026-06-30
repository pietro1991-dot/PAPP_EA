#!/usr/bin/env python3
"""
line_cross_mining.py - LIVELLO 0: mina i pattern LINEA-LINEA (MA incrocia MA),
NON tocca i pattern prezzo-linea esistenti. Riusa il motore di simulazione di
pattern_mining.py (import, nessuna modifica al file originale).

Per ogni incrocio linea-linea (le 6 coppie adiacenti gia' nell'export) prova:
  - direzione NATURALE (segui il cross) e FADE (contro il cross)
  - ogni linea-SL (SL_CANDIDATES) x ogni TP (TP_CANDIDATES)  [stesso grid dei prezzo-linea]
Split train (<2020) / test (>=2020). Tiene solo i pattern ROBUSTI:
  N>=MINN, profittevoli su train E test (PF>1 entrambi). Stampa i sopravvissuti.

Uso: python3 line_cross_mining.py [PAPP_Export.csv] [--spread=15] [--split=2020.01.01] [--minn=30]
"""
import sys, argparse
from collections import defaultdict
from statistics import mean
import pattern_mining as pm   # riuso, NON modifico

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="../EURUSD/PAPP_Export.csv")
    ap.add_argument("--spread", type=float, default=15)   # punti (1.5 pip), come i pattern attuali
    ap.add_argument("--split", default="2020.01.01")
    ap.add_argument("--minn", type=int, default=30)
    ap.add_argument("--all28", action="store_true", help="calcola TUTTE le 28 coppie linea-linea dai valori MA (non solo le 6 adiacenti)")
    return ap.parse_args()

def isok(v):
    try: return 0.0 < float(v) < 1e12
    except: return False

def build_all28_entries(rows):
    """Tutte le C(8,2)=28 coppie linea-linea, calcolate dai valori delle linee.
    Entry quando il segno di (linea_i - linea_j) cambia. dir = +1 se i passa SOPRA j."""
    cols = pm.LINE_COLS   # ['MA365','MA182','MA121','MA30','MA14','MA7','MA3','median']
    names= pm.LINE_NAMES
    ent=[]
    for a in range(len(cols)):
        for b in range(a+1, len(cols)):
            ca,cb=cols[a],cols[b]; tag=f"X{names[a]}_{names[b]}"
            prev=None
            for i in range(len(rows)):
                va,vb=rows[i].get(ca),rows[i].get(cb)
                if not (isok(va) and isok(vb)): prev=None; continue
                s = 1 if float(va)>float(vb) else 0
                if prev is not None and s!=prev:
                    ent.append({'idx':i,'line':tag,'dir':(1 if (prev==0 and s==1) else -1),
                                'price':float(rows[i]['close']),'datetime':rows[i]['datetime'],
                                'ctx':pm.entry_context(rows[i])})
                prev=s
    return ent

def stats(pnls):
    if not pnls: return (0,0.0,0.0,0.0)
    n=len(pnls); tot=sum(pnls); win=sum(1 for p in pnls if p>0)/n*100
    g=sum(p for p in pnls if p>0); l=-sum(p for p in pnls if p<0)
    pf=(g/l) if l>0 else 9.99
    return (n,tot,win,pf)

def main():
    a=parse_args()
    rows=pm.load_csv(a.csv)
    print(f"caricato {a.csv}: {len(rows)} barre")
    # entry LINEA-LINEA: 6 adiacenti (default) o tutte le 28 (--all28)
    if a.all28:
        ent=build_all28_entries(rows)
    else:
        ent=[e for e in pm.detect_entries(rows, include_line_cross=True) if str(e['line']).startswith('X')]
    # conteggio eventi per tipo (rarita')
    cnt=defaultdict(int)
    for e in ent: cnt[e['line']]+=1
    print("eventi linea-linea per tipo:", dict(cnt))
    # versione FADE (direzione opposta), taggata
    fade=[{**e,'dir':-e['dir'],'line':'F:'+e['line']} for e in ent]
    allent = ent+fade
    # grid SL x TP (riusa il simulatore esistente)
    res=pm.analyze_dynamic_sl_grid(allent, rows, spread_pt=a.spread)
    # raggruppa per pattern = (line, dir, sl_line, tp_pt); split per data
    pats=defaultdict(lambda:{'tr':[],'te':[]})
    for r in res:
        key=(r['line'], r['dir'], r['sl_line'], r['tp_pt'])
        bucket='tr' if r['datetime']<a.split else 'te'
        pats[key][bucket].append(r['pnl_pt'])
    # filtro robusto
    surv=[]
    for key,d in pats.items():
        ntr,ttr,wtr,pftr=stats(d['tr']); nte,tte,wte,pfte=stats(d['te'])
        N=ntr+nte
        if N>=a.minn and ntr>=10 and nte>=8 and ttr>0 and tte>0 and pftr>1.0 and pfte>1.0:
            surv.append((key,N,ttr,pftr,wtr,ntr,tte,pfte,wte,nte))
    surv.sort(key=lambda x:-(x[2]+x[6]))   # per profitto train+test
    print(f"\n=== PATTERN LINEA-LINEA SOPRAVVISSUTI (N>={a.minn}, profitto+PF>1 su TRAIN e TEST) ===")
    if not surv:
        print("  NESSUNO. I pattern linea-linea (6 adiacenti) non producono edge robusto OOS.")
    else:
        print(f"{'pattern (entry,dir,SL,TP)':38s} | {'TRAIN N/tot/PF/win':22s} | {'TEST N/tot/PF/win':22s}")
        for key,N,ttr,pftr,wtr,ntr,tte,pfte,wte,nte in surv:
            ln,dr,sl,tp=key
            d='BUY' if dr==1 else 'SELL'
            print(f"  {ln:14s} {d:4s} SL={sl:6s} TP={tp:2d} | N{ntr:3d} {ttr:+7.0f} PF{pftr:.2f} {wtr:3.0f}% | N{nte:3d} {tte:+7.0f} PF{pfte:.2f} {wte:3.0f}%")
    print(f"\n  (totale pattern testati: {len(pats)}, sopravvissuti: {len(surv)})")

if __name__=="__main__":
    main()
