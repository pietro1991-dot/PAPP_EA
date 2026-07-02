#!/usr/bin/env python3
"""
portfolio_majors.py - Reversione H1 su PIU' majors insieme -> curva combinata.
Verifica la tesi: i drawdown dei singoli simboli sono decorrelati, quindi il
portfolio liscia la curva e riduce il -44% del singolo EURUSD.

Ogni simbolo: stessa logica validata (osc = percentile su W della distanza dalla
Median; osc<Lo BUY, osc>Hi SELL; esci a osc=50 / MaxHold). Rischio SPLITTATO:
ogni simbolo pesa 1/N del capitale, cosi' il rischio totale resta costante.

Uso:
  python3 portfolio_majors.py ../data/scalp_EURUSD_h1.csv [../data/scalp_GBPUSD_h1.csv ...] \
          [--cost=30] [--split=2020.01.01] [--cap=10000] [--pct=25]

Output: per-simbolo (Net,PF,DD) + PORTFOLIO combinato + correlazione dei ritorni mensili.
"""
import sys, numpy as np
from numpy.lib.stride_tricks import sliding_window_view

PATHS=[]; COST=30.0; SPLIT="2020.01.01"; CAP=10000.0; PCT=25.0
W=300; LO=5.0; HI=95.0; MAXHOLD=48; PT=1e-5
VOLTGT=False; VFAST=40; VSLOW=6000; VFLOOR=0.30; VCAP=2.50
for a in sys.argv[1:]:
    if a.startswith("--cost="): COST=float(a.split("=")[1])
    elif a.startswith("--split="): SPLIT=a.split("=")[1]
    elif a.startswith("--cap="): CAP=float(a.split("=")[1])
    elif a.startswith("--pct="): PCT=float(a.split("=")[1])
    elif a=="--voltarget": VOLTGT=True
    elif a.startswith("--vslow="): VSLOW=int(a.split("=")[1])
    elif not a.startswith("--"): PATHS.append(a)
if not PATHS: print("Serve almeno un CSV h1."); sys.exit(1)
N=len(PATHS)

def sym_name(p):
    import os; b=os.path.basename(p)
    for s in ("EURUSD","GBPUSD","USDCHF","AUDUSD","USDJPY","NZDUSD","USDCAD"):
        if s in b: return s
    return b

def load(path):
    hdr=open(path).readline().strip().split(","); ix={h:i for i,h in enumerate(hdr)}
    close=np.genfromtxt(path,delimiter=",",skip_header=1,usecols=[ix["close"]],dtype=float)
    dmed =np.genfromtxt(path,delimiter=",",skip_header=1,usecols=[ix["dMed"]],dtype=float)
    dts  =np.genfromtxt(path,delimiter=",",skip_header=1,usecols=[0],dtype="U16")
    n=len(close)
    osc=np.full(n,np.nan); win=sliding_window_view(dmed,W); osc[W-1:]=(win<=dmed[W-1:][:,None]).mean(1)*100
    return dts,close,osc

def vol_factor_series(close):
    """Come VolFactor() dell'EA: clamp(std_lenta/std_veloce, floor, cap) per ogni barra.
    Ritorna array (nan finche' non c'e' storia). Size scende quando la vol RECENTE e' alta."""
    n=len(close); f=np.full(n,1.0)
    if not VOLTGT: return f
    r=np.zeros(n); r[1:]=np.log(close[1:]/close[:-1])
    # rolling std veloce e lenta
    sf=sliding_window_view(r,VFAST).std(1,ddof=1)   # indice i -> finestra [i, i+VFAST)
    ss=sliding_window_view(r,VSLOW).std(1,ddof=1)
    f[:]=np.nan
    for j in range(VSLOW, n):
        fast=sf[j-VFAST+1] if j-VFAST+1>=0 else np.nan   # finestra che TERMINA a j
        slow=ss[j-VSLOW+1] if j-VSLOW+1>=0 else np.nan
        if fast and fast>0 and np.isfinite(slow):
            f[j]=max(VFLOOR, min(VCAP, slow/fast))
        else: f[j]=1.0
    return f

def backtest(dts,close,osc,cap_share):
    """Ritorna lista (t_exit, pnl_eur). Size FISSA sul capitale iniziale della quota
    (no compounding). Con --voltarget la size viene scalata dal fattore-vol all'ENTRATA."""
    n=len(close); lot=(cap_share/10000.0)*(PCT/100.0)
    ppp = 100000*PT*lot
    vf=vol_factor_series(close)
    pos=0;entry=0;ej=0;dirn=0;fac=1.0;tr=[]
    for j in range(W,n-1):
        o=osc[j]
        if o!=o: continue
        if pos==0:
            d=1 if o<LO else (-1 if o>HI else 0)
            if d!=0:
                pos,dirn,ej,entry=1,d,j,close[j]
                fac=vf[j] if (VOLTGT and np.isfinite(vf[j])) else 1.0
        else:
            ex=(dirn==1 and o>=50) or (dirn==-1 and o<=50) or (j-ej)>=MAXHOLD
            if ex:
                pts=dirn*(close[j]-entry)/PT-COST
                tr.append((dts[j], pts*ppp*fac)); pos=0
    return tr

def dd_of(pnls, base):
    """Max drawdown (EUR, %) di una lista (t,pnl) partendo da base."""
    if not pnls: return 0.0,0.0
    eq=base+np.cumsum([p for _,p in pnls]); peak=np.maximum.accumulate(eq)
    dd=peak-eq; return dd.max(), (100*dd/peak).max()

def window_stats(pnls, base, lo, hi):
    """Stat su un sotto-periodo [lo,hi) (stringhe datetime)."""
    sub=[(t,p) for t,p in pnls if lo<=t<hi]
    p=np.array([x[1] for x in sub])
    if len(p)<5: return None
    w=p[p>0]; l=p[p<0]; pf=w.sum()/abs(l.sum()) if l.sum() else 9.9
    dde,ddp=dd_of(sub,base)
    return dict(net=p.sum(),pf=pf,win=100*len(w)/len(p),n=len(p),dde=dde,ddp=ddp)

def stats(pnls):
    p=np.array([x[1] for x in pnls])
    if len(p)<5: return None
    w=p[p>0]; l=p[p<0]; pf=w.sum()/abs(l.sum()) if l.sum() else 9.9
    return dict(net=p.sum(),pf=pf,win=100*len(w)/len(p),n=len(p))

# --- per simbolo ---
share=CAP/N
all_tr={}
print(f"Portfolio reversione H1 | simboli={N} | cost={COST}pt | cap={CAP:.0f} (quota {share:.0f}/simbolo) | pct={PCT}\n")
print(f"{'simbolo':8} | {'Net EUR':>9} {'PF':>5} {'win':>4} {'N':>5} {'MaxDD€':>8} {'MaxDD%':>6}")
print("-"*60)
for p in PATHS:
    dts,close,osc=load(p); tr=backtest(dts,close,osc,share); all_tr[sym_name(p)]=tr
    s=stats(tr)
    eq=share+np.cumsum([x[1] for x in tr]); dd=np.maximum.accumulate(eq)-eq
    ddp=100*dd/np.maximum.accumulate(eq)
    print(f"{sym_name(p):8} | {s['net']:>9.0f} {s['pf']:>5.2f} {s['win']:>3.0f}% {s['n']:>5} {dd.max():>8.0f} {ddp.max():>5.1f}%")

# --- portfolio combinato: unisci tutti i trade su timeline comune ---
events=[]
for sym,tr in all_tr.items():
    for t,pnl in tr: events.append((t,pnl))
events.sort(key=lambda x:x[0])
eq=CAP; curve=[]; times=[]
for t,pnl in events: eq+=pnl; curve.append(eq); times.append(t)
curve=np.array(curve)
dd=np.maximum.accumulate(curve)-curve; ddp=100*dd/np.maximum.accumulate(curve)
net=curve[-1]-CAP
gp=sum(p for _,p in events if p>0); gl=sum(p for _,p in events if p<0)
print("-"*60)
print(f"{'PORTFOLIO':8} | {net:>9.0f} {gp/abs(gl) if gl else 9.9:>5.2f} {'':>4} {len(events):>5} {dd.max():>8.0f} {ddp.max():>5.1f}%")
print(f"\nSaldo finale: {curve[-1]:.0f} (da {CAP:.0f})  |  Max DrawDown portfolio: {ddp.max():.1f}%")

# --- correlazione dei ritorni MENSILI tra simboli (piu' bassa = piu' diversificazione) ---
if N>1:
    def monthly(tr):
        d={}
        for t,pnl in tr: d[t[:7]]=d.get(t[:7],0)+pnl
        return d
    months=sorted(set().union(*[set(monthly(tr)) for tr in all_tr.values()]))
    M=np.array([[monthly(all_tr[s]).get(m,0) for m in months] for s in all_tr])
    syms=list(all_tr); C=np.corrcoef(M)
    print("\nCorrelazione ritorni MENSILI (bassa = i DD non coincidono = portfolio piu' liscio):")
    print("        "+" ".join(f"{s:>7}" for s in syms))
    for i,s in enumerate(syms):
        print(f"{s:>7} "+" ".join(f"{C[i,j]:>7.2f}" for j in range(len(syms))))

# --- SPLIT TRAIN/TEST: il test di robustezza vero (regge fuori campione?) ---
print(f"\n{'='*66}\nROBUSTEZZA — split al {SPLIT[:4]}: TRAIN < {SPLIT[:4]} <= TEST\n{'='*66}")
print(f"{'':8} | {'periodo':6} | {'Net EUR':>9} {'PF':>5} {'win':>4} {'N':>5} {'MaxDD%':>6}")
print("-"*66)
for sym,tr in list(all_tr.items()):
    for lbl,lo,hi in [("TRAIN","0000",SPLIT[:4]),("TEST",SPLIT[:4],"9999")]:
        s=window_stats(tr, share, lo, hi)
        if s: print(f"{sym:8} | {lbl:6} | {s['net']:>9.0f} {s['pf']:>5.2f} {s['win']:>3.0f}% {s['n']:>5} {s['ddp']:>5.1f}%")
    print("-"*66)
for lbl,lo,hi in [("TRAIN","0000",SPLIT[:4]),("TEST",SPLIT[:4],"9999")]:
    s=window_stats(events, CAP, lo, hi)
    if s: print(f"{'PORTAF.':8} | {lbl:6} | {s['net']:>9.0f} {s['pf']:>5.2f} {'':>4} {s['n']:>5} {s['ddp']:>5.1f}%")
print("-"*66)
print("Verdetto: se il PORTFOLIO resta PF>1 e DD contenuto ANCHE in TEST -> robusto = vendibile.")