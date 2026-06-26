#!/usr/bin/env python3
"""
Genera PATTERNS_<SIMBOLO>.md: schede di validazione dei pattern.

- Legge il CSV del simbolo + il file EA (.mq5) per sapere quali pattern sono
  configurati (entry/exit/SL/SLpips/TP/trail/dir, ON/OFF).
- Simula ogni pattern con la STESSA logica di uscita dell'EA (cross-exit, SL su
  linea, disaster stop fisso, TP fisso, trailing) e le UNITA' giuste:
    TP = pip (tp*10*point)   SLpips/trail = pip (*10*point)
- Calcola train/test (split) e produce un Markdown: tabella + scheda per pattern
  dell'EA, + appendice coi candidati base robusti (positivi train E test).

Uso:
  python3 genera_schede.py <CSV> <EA.mq5> <SIMBOLO> [--split=2020.01.01] [--spread=15] [--comm=7]
Output: PATTERNS_<SIMBOLO>.md nella cartella corrente.
"""
import sys, re, os, statistics

PT  = 0.00001          # 1 punto (simboli a 5 decimali)
PIP = 10 * PT          # 1 pip
MAXB = 200             # barre massime di tenuta

LINES = {0:'median',3:'MA3',7:'MA7',14:'MA14',30:'MA30',121:'MA121',182:'MA182',365:'MA365'}
CROSS = {0:'crossMed',3:'crossMA3',7:'crossMA7',14:'crossMA14',30:'crossMA30',
         121:'crossMA121',182:'crossMA182',365:'crossMA365'}
SL_GRID = [14,30,121,365,0]                       # linee SL candidate (come il miner)
TP_GRID = [2,3,4,5,6,8,10,12,15]                  # TP candidati (PIP)

def lname(n): return 'Median' if n==0 else f'MA{n}'
def dname(d): return 'BUY' if d==1 else 'SELL'

# ---------- caricamento ----------
def load(csv):
    import csv as c
    with open(csv, newline='') as f:
        return list(c.DictReader(f))

def build(rows):
    n=len(rows)
    H=[float(r['high']) for r in rows]; L=[float(r['low']) for r in rows]; C=[float(r['close']) for r in rows]
    line={k:[float(r[col]) for r in rows] for k,col in LINES.items()}
    cross={k:[int(r[col]) for r in rows] for k,col in CROSS.items()}
    dt=[r['datetime'] for r in rows]
    return (H,L,C,line,cross,dt,n)

# ---------- simulatore unico (logica EA) ----------
def sim_one(A, idx, p, spread, comm):
    H,L,C,line,cross,dt,n = A
    buy = (p['dir']==1); ep=C[idx]; cost=spread+comm
    exitk=p['exit']; slk=p['sl']; slpips=p['slpips']; tp=p['tp']; ta=p['trailact']; tg=p['trailgive']
    want = -1 if buy else 1
    # SL su linea: salta l'entrata se la linea e' dal lato sbagliato (come EA/miner)
    if slk:
        sv0=line[slk][idx]
        if not (sv0>0): return None
        if buy and sv0>=ep: return None
        if (not buy) and sv0<=ep: return None
    slfix = (ep - slpips*PIP) if (slpips and not slk and buy) else ((ep + slpips*PIP) if (slpips and not slk) else None)
    tplvl = (ep + tp*PIP) if (tp and buy) else ((ep - tp*PIP) if tp else None)
    best = ep
    end=min(idx+MAXB, n)
    for j in range(idx+1, end):
        # SL su linea (valore barra j-1: niente look-ahead)
        if slk:
            sv=line[slk][j-1]
            if sv>0:
                if buy and L[j]<=sv: return (sv-ep)/PT-cost, j
                if (not buy) and H[j]>=sv: return (ep-sv)/PT-cost, j
        # disaster stop fisso
        if slfix is not None:
            if buy and L[j]<=slfix: return (slfix-ep)/PT-cost, j
            if (not buy) and H[j]>=slfix: return (ep-slfix)/PT-cost, j
        # TP (pip)
        if tplvl is not None:
            if buy and H[j]>=tplvl: return (tplvl-ep)/PT-cost, j
            if (not buy) and L[j]<=tplvl: return (ep-tplvl)/PT-cost, j
        # trailing profit (pip)
        if tg:
            best = max(best,H[j]) if buy else min(best,L[j])
            prof = (best-ep)/PIP if buy else (ep-best)/PIP
            if prof>=ta:
                ts = best - tg*PIP if buy else best + tg*PIP
                if buy and L[j]<=ts: return (ts-ep)/PT-cost, j
                if (not buy) and H[j]>=ts: return (ep-ts)/PT-cost, j
        # uscita su crossover (a chiusura)
        if exitk and cross[exitk][j]==want:
            return (((C[j]-ep) if buy else (ep-C[j]))/PT-cost), j
    j=end-1
    if j>idx:
        return (((C[j]-ep) if buy else (ep-C[j]))/PT-cost), j
    return None

def run(A, p, spread, comm):
    """Portafoglio 1-posizione-alla-volta. Ritorna lista pnl (punti)."""
    H,L,C,line,cross,dt,n = A
    buy=(p['dir']==1); want=1 if buy else -1; entk=p['entry']
    last=-1; out=[]
    for idx in range(n):
        if cross[entk][idx]!=want: continue
        if idx<=last: continue
        o=sim_one(A, idx, p, spread, comm)
        if o: out.append(o[0]); last=o[1]
    return out

def _sharpe(pn):
    # Sharpe per-trade con difesa CV<10% (come il miner): azzera gli Sharpe
    # finti dei pattern dominati da un TP minuscolo (tutti i trade quasi uguali).
    if len(pn)<2: return 0.0
    avg=sum(pn)/len(pn)
    try: sd=statistics.stdev(pn)
    except Exception: return 0.0
    if sd==0 or (avg!=0 and sd<0.10*abs(avg)): return 0.0
    return avg/sd

def metrics(pn):
    if not pn: return None
    w=sum(1 for x in pn if x>0)
    eq=pk=mdd=0
    for x in pn: eq+=x; pk=max(pk,eq); mdd=max(mdd,pk-eq)
    return dict(n=len(pn), wins=w, win=w/len(pn)*100, pnl=sum(pn),
                mdd=mdd, retdd=(sum(pn)/mdd if mdd>0 else float('inf')),
                sharpe=_sharpe(pn))

# ---------- parsing EA ----------
def parse_ea(path):
    s=open(path, encoding='utf-8-sig', errors='ignore').read()
    def iv(name):
        m=re.search(rf'\b{name}\s*=\s*(-?\d+)', s); return int(m.group(1)) if m else 0
    def bv(name):
        m=re.search(rf'\b{name}\s*=\s*(true|false)', s); return (m.group(1)=='true') if m else False
    def grp(i):
        m=re.search(rf'input group "==\s*P{i}\s*-\s*([^=]*?)\s*=="', s)
        return m.group(1).strip() if m else ''
    nslot=len(set(re.findall(r'InpP(\d+)_On\s*=', s)))
    pats=[]
    for i in range(1, nslot+1):
        if not re.search(rf'InpP{i}_On\s*=', s): continue
        pats.append(dict(id=i, on=bv(f'InpP{i}_On'), entry=iv(f'InpP{i}_Entry'),
            exit=iv(f'InpP{i}_Exit'), sl=iv(f'InpP{i}_SL'), slpips=iv(f'InpP{i}_SLpips'),
            tp=iv(f'InpP{i}_TP'), trailact=iv(f'InpP{i}_TrailAct'),
            trailgive=iv(f'InpP{i}_TrailGive'), dir=iv(f'InpP{i}_Dir'), label=grp(i)))
    return pats

def descr(p):
    s=f"{lname(p['entry'])} {dname(p['dir'])}"
    if p['exit']>0: s+=f" → cross{lname(p['exit'])}"
    bits=[]
    if p['sl']>0: bits.append(f"SL={lname(p['sl'])}")
    if p['slpips']>0: bits.append(f"SLfix={p['slpips']}pip")
    if p['tp']>0: bits.append(f"TP={p['tp']}pip")
    if p['trailgive']>0: bits.append(f"trail {p['trailgive']}pip")
    if bits: s+=" ["+", ".join(bits)+"]"
    return s

# ---------- main ----------
def main():
    csv, ea_path, sym = sys.argv[1], sys.argv[2], sys.argv[3]
    split='2020.01.01'; spread=15; comm=7.0
    for a in sys.argv[4:]:
        if a.startswith('--split='): split=a.split('=',1)[1]
        elif a.startswith('--spread='): spread=int(a.split('=',1)[1])
        elif a.startswith('--comm='): comm=float(a.split('=',1)[1])

    rows=load(csv)
    tr=[r for r in rows if r['datetime']<split]
    te=[r for r in rows if r['datetime']>=split]
    Atr, Ate = build(tr), build(te)
    pats=parse_ea(ea_path)

    def stat(A,p):
        m=metrics(run(A,p,spread,comm)); return m

    out=[]
    w=out.append
    w(f"# Pattern {sym} — schede di validazione\n")
    w(f"> Generato da `genera_schede.py` · split **{split}** · costi spread={spread} comm={comm} · "
      f"portafoglio 1 posizione/volta.")
    w(f"> Numeri in **PUNTI** (1 pip = 10 punti). \"Successi\" = trade chiusi in profitto. "
      f"TEST = out-of-sample (≥ split).\n")

    # tabella riassuntiva pattern EA
    w("## Pattern dell'EA\n")
    w("| # | Pattern | Stato | TestN | Successi | Win% | PnL test | Ret/DD | PnL train |")
    w("|---|---|---|---|---|---|---|---|---|")
    cards=[]
    for p in pats:
        mt=stat(Ate,p); mr=stat(Atr,p)
        on='✅ ON' if p['on'] else '⬜ OFF'
        if mt:
            rdd = '∞' if mt['retdd']==float('inf') else f"{mt['retdd']:.2f}"
            w(f"| P{p['id']} | {descr(p)} | {on} | {mt['n']} | {mt['wins']} | {mt['win']:.0f}% | "
              f"{mt['pnl']:+.0f} | {rdd} | {mr['pnl']:+.0f} |" if mr else
              f"| P{p['id']} | {descr(p)} | {on} | {mt['n']} | {mt['wins']} | {mt['win']:.0f}% | {mt['pnl']:+.0f} | {rdd} | — |")
        else:
            w(f"| P{p['id']} | {descr(p)} | {on} | — | — | — | — | — | — |")
        cards.append((p,mt,mr))

    # schede dettagliate
    w("\n## Schede\n")
    for p,mt,mr in cards:
        w(f"### P{p['id']} — {descr(p)}")
        if p['label']: w(f"*{p['label']}*  ")
        w(f"- **Stato:** {'ON' if p['on'] else 'OFF'} · **Direzione:** {dname(p['dir'])} · "
          f"**Entrata:** cross prezzo×{lname(p['entry'])}")
        ex = (f"cross×{lname(p['exit'])}" if p['exit']>0 else "")
        prot=[]
        if p['sl']>0: prot.append(f"SL dinamico su {lname(p['sl'])}")
        if p['slpips']>0: prot.append(f"disaster stop {p['slpips']} pip")
        if p['tp']>0: prot.append(f"TP {p['tp']} pip")
        if p['trailgive']>0: prot.append(f"trailing {p['trailgive']} pip (attiva +{p['trailact']})")
        w(f"- **Uscita:** {ex if ex else '—'}" + (f" · **Protezioni:** {', '.join(prot)}" if prot else ""))
        if mt:
            rdd = '∞' if mt['retdd']==float('inf') else f"{mt['retdd']:.2f}"
            w(f"- **Test OOS:** {mt['n']} trade, **{mt['wins']} successi ({mt['win']:.0f}%)**, "
              f"PnL **{mt['pnl']:+.0f}**, Ret/DD {rdd}, MaxDD {mt['mdd']:.0f}")
        if mr:
            w(f"- **Train:** {mr['n']} trade, {mr['wins']} successi ({mr['win']:.0f}%), PnL {mr['pnl']:+.0f}")
        w("")

    # appendice: candidati base robusti (positivi train E test)
    w("## Appendice — candidati base robusti (positivi train E test)\n")
    w("> Tutti i pattern base (entry prezzo-linea; exit su cross **oppure** SL+TP) che restano "
      "in attivo sia su train sia su test. Ordinati per Ret/DD del test.")
    cand=[]
    for entry in LINES:
        for d in (1,-1):
            # SPEC: uscita su ogni linea
            for ex in LINES:
                if ex==0 and entry==0: pass
                p=dict(entry=entry,dir=d,exit=ex,sl=0,slpips=0,tp=0,trailact=0,trailgive=0)
                mr=metrics(run(Atr,p,spread,comm)); mt=metrics(run(Ate,p,spread,comm))
                if (mr and mt and mr['n']>=15 and mt['n']>=8 and mr['pnl']>0 and mt['pnl']>0
                        and mt['mdd']>0 and mt['sharpe']!=0):
                    cand.append((f"{lname(entry)} {dname(d)} → cross{lname(ex)}", mt))
            # GRID: SL linea + TP
            for slk in SL_GRID:
                for tpv in TP_GRID:
                    p=dict(entry=entry,dir=d,exit=0,sl=slk,slpips=0,tp=tpv,trailact=0,trailgive=0)
                    mr=metrics(run(Atr,p,spread,comm)); mt=metrics(run(Ate,p,spread,comm))
                    if (mr and mt and mr['n']>=15 and mt['n']>=8 and mr['pnl']>0 and mt['pnl']>0
                        and mt['mdd']>0 and mt['sharpe']!=0):
                        cand.append((f"{lname(entry)} {dname(d)} SL={lname(slk)} TP={tpv}pip", mt))
    cand.sort(key=lambda x: -(x[1]['retdd'] if x[1]['retdd']!=float('inf') else 999))
    w(f"\nCandidati robusti: **{len(cand)}**\n")
    w("| Pattern | TestN | Successi | Win% | PnL test | Ret/DD |")
    w("|---|---|---|---|---|---|")
    for lbl,m in cand[:40]:
        rdd='∞' if m['retdd']==float('inf') else f"{m['retdd']:.2f}"
        w(f"| {lbl} | {m['n']} | {m['wins']} | {m['win']:.0f}% | {m['pnl']:+.0f} | {rdd} |")

    txt="\n".join(out)+"\n"
    fn=f"PATTERNS_{sym}.md"
    open(fn,'w').write(txt)
    print(f"Scritto {fn} ({len(pats)} pattern EA, {len(cand)} candidati robusti)")

if __name__=='__main__':
    main()
