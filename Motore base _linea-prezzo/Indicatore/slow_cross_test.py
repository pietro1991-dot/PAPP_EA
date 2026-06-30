#!/usr/bin/env python3
"""
slow_cross_test.py - Due indagini (file nuovo, non tocca nulla):
A) GEOMETRIA vs TIMING: entrate CASUALI con TP15/SL-MA365 fanno soldi? (se sì, l'edge
   dei pattern scalp è geometria, non timing del cross).
B) IDEA UTENTE: i cross LENTI (es. MA182 spacca MA365) sono inversioni vere? Li testo
   come entrata di TREND (direzione del cross), misurando il rendimento futuro nella
   direzione del cross a vari orizzonti, e il P&L "cavalca fino al cross opposto".
Dati: export EURUSD D1.
"""
import random
from statistics import mean, pstdev
import pattern_mining as pm
random.seed(7)
rows=pm.load_csv("../EURUSD/PAPP_Export.csv")
n=len(rows); PT=pm.PT_SIZE
def f(r,c):
    try: return float(r[c])
    except: return None
close=[f(r,'close') for r in rows]

print("=== A) GEOMETRIA vs TIMING: entrate CASUALI, TP15 / SL=MA365 ===")
sl_col='MA365'
for buy in (True,False):
    pool=[i for i in range(n-2) if (lambda sv,pr: sv and pr and 0<sv<1e12 and ((sv<pr) if buy else (sv>pr)))(f(rows[i],sl_col),close[i])]
    pnls=[]
    for i in random.sample(pool,min(400,len(pool))):
        o=pm.simulate_trade(rows,i,buy,close[i],sl_col,15,15)
        if o: pnls.append(o[0])
    print(f"  {'BUY ' if buy else 'SELL'} casuale: N={len(pnls)} EV={mean(pnls):+.1f}pt win={sum(1 for p in pnls if p>0)/len(pnls)*100:.0f}% tot={sum(pnls):+.0f}")
print("  -> se EV>0, il profilo TP-stretto/SL-MA365 rende ANCHE a caso = geometria, non timing.\n")

# B) cross LENTI come entrata di trend
print("=== B) CROSS LENTI come INVERSIONE/TREND (idea utente) ===")
def cross_events(ca,cb):
    """eventi quando ca incrocia cb. dir=+1 se ca passa SOPRA cb (es. 182 sopra 365 = uptrend)."""
    ev=[]; prev=None
    for i in range(n):
        va,vb=f(rows[i],ca),f(rows[i],cb)
        if not (va and vb and 0<va<1e12 and 0<vb<1e12): prev=None; continue
        s=1 if va>vb else 0
        if prev is not None and s!=prev: ev.append((i, 1 if (prev==0 and s==1) else -1))
        prev=s
    return ev
H=[10,20,60,120]
# baseline drift per orizzonte (media incondizionata della |variazione| con segno casuale ~0; uso media semplice)
def fwd(i,h,d):
    if i+h>=n or close[i] is None or close[i+h] is None: return None
    return (close[i+h]-close[i])/PT*d
for ca,cb in [('MA182','MA365'),('MA121','MA365'),('MA121','MA182'),('MA30','MA365'),('MA30','MA121')]:
    ev=cross_events(ca,cb)
    print(f"\n  {ca} x {cb}  (N eventi={len(ev)}):")
    row=[]
    for h in H:
        rs=[fwd(i,h,d) for (i,d) in ev]; rs=[x for x in rs if x is not None]
        if rs: row.append(f"+{h}b:{mean(rs):+6.0f}pt(N{len(rs)})")
    print("   rendimento futuro NELLA direzione del cross:", "  ".join(row))
    # P&L: cavalca fino al cross opposto (exit quando ca re-incrocia cb)
    trades=[]
    for k,(i,d) in enumerate(ev):
        # trova il prossimo evento (cross opposto) come uscita
        nxt=ev[k+1][0] if k+1<len(ev) else min(i+250,n-1)
        if close[i] is None or close[nxt] is None: continue
        trades.append((close[nxt]-close[i])/PT*d - 15)   # -spread
    if len(trades)>=5:
        tot=sum(trades); win=sum(1 for t in trades if t>0)/len(trades)*100
        g=sum(t for t in trades if t>0); l=-sum(t for t in trades if t<0); pf=g/l if l>0 else 9.99
        print(f"   'cavalca fino al cross opposto': N={len(trades)} tot={tot:+.0f}pt win={win:.0f}% PF={pf:.2f} EV={tot/len(trades):+.0f}")
print("\n  (rendimento futuro >0 = il cross predice un trend nella sua direzione = l'idea regge)")
