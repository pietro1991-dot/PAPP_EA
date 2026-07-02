#!/usr/bin/env python3
"""
exit_grid_R.py - GRIGLIA DI USCITA sui 6 pattern veri, scorata in R (file nuovo, non tocca l'EA).

Contesto (dd_anatomy.py): il motore base e' skew-negativo sul filo: vincita media +0.05R,
perdita -1R, Ret/DD(soldi) ~1. La leva NON e' l'entry ma lo SKEW dell'uscita: far correre
i vincitori per alzare la vincita media. Qui provo varianti di USCITA tenendo entry+SL
identici (stessa distanza di rischio -> R confrontabile tra varianti) e misuro in R.

R = pnl_pt / distanza-rischio-iniziale(entry->SL a apertura). Denominatore COSTANTE tra
varianti -> confronto onesto (l'EA dimensiona su quella distanza: +X R = +X*RiskPct sui soldi).

Guardie EA replicate: SL dal lato giusto, InpMinSLDistPips=5 (risk>=50pt).
Portafoglio 1-posizione/volta per variante (l'uscita cambia quando si libera il capitale).
Split TRAIN<2020 / TEST>=2020, spread 1.5pip.

Varianti di uscita:
  BASE            TP fisso del pattern + SL dinamico su linea-pattern (=motore attuale)
  TP<n>           TP fisso a n pip (SL dinamico invariato)              -> vincitori piu' larghi
  TRAIL           niente TP: cavalca il SL dinamico su linea-pattern    -> lascia correre tutto
  TRAILx<MA>      niente TP: esci quando il prezzo rientra oltre <MA> (protettivo=SL-pattern)
  RUN<f>x<MA>     frazione (1-f) esce al TP del pattern, f cavalca ed esce su rientro <MA>
"""
from statistics import mean
import pattern_mining as pm
PT=pm.PT_SIZE; PIP=pm.PIP_SIZE; MAXB=pm.MAX_BARS
CSV="../EURUSD/PAPP_Export.csv"; SPLIT="2020.01.01"; SPREAD=15
PATTERNS=[("P1","MA30",-1,"MA365",15),("P2","MA121",1,"MA365",15),
          ("P3","MA365",-1,"MA121",12),("P4","MA7",-1,"MA365",12),
          ("P5","MA30",1,"MA365",15),("P6","MA14",1,"MA365",15)]

def fnum(x):
    try: return float(x)
    except: return None

def build_events(rows):
    ents=pm.detect_entries(rows); idx_by={}
    for e in ents: idx_by.setdefault((e['line'],e['dir']),[]).append(e)
    ev=[]
    for name,entry,d,sl,tp in PATTERNS:
        sl_col=pm.LINE_COLS[pm.LINE_NAMES.index(sl)]; buy=(d==1)
        for e in idx_by.get((entry,d),[]):
            i=e['idx']; sv=fnum(rows[i].get(sl_col))
            if sv is None or not(0<sv<1e12): continue
            if buy and sv>=e['price']: continue
            if (not buy) and sv<=e['price']: continue
            if abs(e['price']-sv)/PT < 50: continue
            ev.append({'pat':name,'idx':i,'buy':buy,'price':e['price'],
                       'sl_col':sl_col,'tp':tp,'dt':rows[i]['datetime']})
    ev.sort(key=lambda x:x['idx']); return ev

def sim(rows, ev, tp_pt, f_run, exit_col):
    """Ritorna (R, exit_idx). f_run=frazione runner (0=tutto al TP). exit_col=linea di rientro
    per il runner (None=cavalca il SL-pattern fino a touch/timeout). Protettivo=sempre sl_col."""
    idx=ev['idx']; buy=ev['buy']; price=ev['price']; sl_col=ev['sl_col']
    risk0=abs(price-fnum(rows[idx][sl_col]))
    if risk0<=0: return None
    up=price+tp_pt*PIP; dn=price-tp_pt*PIP
    tp_frac=1.0-f_run
    taken=False; booked=0.0   # punti gia' incassati dalla frazione TP
    end=min(idx+MAXB,len(rows))
    for j in range(idx+1,end):
        sv=fnum(rows[j-1][sl_col]); hi=fnum(rows[j]['high']); lo=fnum(rows[j]['low'])
        # 1) SL protettivo (disaster) sulla linea-pattern: tocca -> chiude il residuo
        if sv and ((buy and lo<=sv) or ((not buy) and hi>=sv)):
            move=(sv-price) if buy else (price-sv)
            frac=(f_run if taken else 1.0)
            pnl=booked+frac*move/PT-SPREAD
            return pnl/(risk0/PT), j
        # 2) TP fisso (solo frazione tp), una volta
        if tp_pt>0 and not taken:
            if (buy and hi>=up) or ((not buy) and lo<=dn):
                if f_run<=0.0:                      # niente runner: esci tutto
                    return (tp_pt*10-SPREAD)/(risk0/PT), j
                booked=tp_frac*tp_pt*10; taken=True  # incassa TP frac, il runner continua
        # 3) uscita runner su rientro linea veloce (dopo che il runner e' l'unico attivo,
        #    o sempre se non c'e' TP): prezzo torna oltre exit_col
        if exit_col and (taken or tp_pt<=0):
            ev_line=fnum(rows[j-1][exit_col])
            close=fnum(rows[j]['close'])
            if ev_line and ((buy and close<ev_line) or ((not buy) and close>ev_line)):
                move=(close-price) if buy else (price-close)
                frac=(f_run if taken else 1.0)
                pnl=booked+frac*move/PT-SPREAD
                return pnl/(risk0/PT), j
    # timeout: residuo mark-to-market
    j=end-1
    if j>idx:
        close=fnum(rows[j]['close']); move=(close-price) if buy else (price-close)
        frac=(f_run if taken else 1.0)
        pnl=booked+frac*move/PT-SPREAD
        return pnl/(risk0/PT), j
    return None

def portfolio(rows, variant):
    tp_pt,f_run,exit_col=variant
    Rs=[]; last=-1
    for ev in build_events(rows):
        if ev['idx']<=last: continue
        tp=ev['tp'] if tp_pt=='pat' else tp_pt
        out=sim(rows,ev,tp,f_run,exit_col)
        if out is None: continue
        R,ex=out; Rs.append(R); last=ex
    if not Rs: return None
    eq=0.0;peak=0.0;mdd=0.0
    for r in Rs: eq+=r;peak=max(peak,eq);mdd=max(mdd,peak-eq)
    w=[r for r in Rs if r>0]; l=[r for r in Rs if r<=0]
    return {'n':len(Rs),'tot':eq,'mdd':mdd,'retdd':(eq/mdd if mdd>0 else float('inf')),
            'win':len(w)/len(Rs)*100,'aw':mean(w) if w else 0,'al':mean(l) if l else 0}

VARIANTS=[
    ("BASE",        ('pat',0.0,None)),
    ("TP20",        (20,  0.0,None)),
    ("TP30",        (30,  0.0,None)),
    ("TP50",        (50,  0.0,None)),
    ("TP80",        (80,  0.0,None)),
    ("TP120",       (120, 0.0,None)),
    ("TRAIL(MA365)",(0,   1.0,None)),
    ("TRAILx MA30", (0,   1.0,'MA30')),
    ("TRAILx MA14", (0,   1.0,'MA14')),
    ("RUN.5x MA30", ('pat',0.5,'MA30')),
    ("RUN.5x MA14", ('pat',0.5,'MA14')),
    ("RUN.3x MA30", ('pat',0.7,'MA30')),
]

def main():
    rows=pm.load_csv(CSV)
    tr=[r for r in rows if r['datetime']<SPLIT]; te=[r for r in rows if r['datetime']>=SPLIT]
    print(f"EURUSD | train {len(tr)} / test {len(te)} barre | R = pnl/rischio-iniziale | 1 pos/volta\n")
    print(f"  {'variante':<14} | {'TRAIN  TotR':>10} {'MaxDD':>6} {'Ret/DD':>7} {'win%':>5} {'avgW':>6} {'avgL':>6}"
          f" | {'TEST  TotR':>10} {'MaxDD':>6} {'Ret/DD':>7} {'win%':>5} {'avgW':>6} {'avgL':>6}")
    print("  "+"-"*128)
    for name,v in VARIANTS:
        a=portfolio(tr,v); b=portfolio(te,v)
        def f(m):
            if not m: return f"{'n/a':>10}"
            rd=f"{m['retdd']:>7.2f}" if m['retdd']!=float('inf') else "    inf"
            return f"{m['tot']:>+10.1f} {m['mdd']:>6.1f} {rd} {m['win']:>4.0f}% {m['aw']:>+6.2f} {m['al']:>+6.2f}"
        print(f"  {name:<14} | {f(a)} | {f(b)}")
    print("\nBASE deve ~riprodurre dd_anatomy (train ~+4R). Cerco varianti con Ret/DD(R)>1 su")
    print("TRAIN *e* TEST e avgW piu' alto di +0.05R senza far crollare win% sotto il break-even.")

if __name__=="__main__": main()
