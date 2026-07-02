#!/usr/bin/env python3
"""
dd_anatomy.py - ANATOMIA del drawdown del motore base EURUSD (file nuovo, non tocca nulla).

Domanda: il MaxDD del portafoglio P1-P6 e' (a) un cluster di perdite correlate in un
periodo, (b) poche botte grosse (SL dinamico su MA365 lontana), (c) colpa di un pattern?
Capire questo dice DOVE intervenire (per pattern? per size? per periodo/regime?).

Metodo: ricostruisco il portafoglio 1-posizione/volta (come pattern_mining / p6_velgate),
tengo date e pattern di ogni trade, poi:
  1) individuo la finestra di MaxDD (picco->minimo) e ci elenco dentro i trade;
  2) attribuisco le perdite per pattern (somma perdite, peggior singola, N loss);
  3) distribuzione: quanta parte del totale perdite viene dai top-K trade peggiori;
  4) profilo asimmetria: vincita media vs perdita media, per pattern.
Split TRAIN<2020 / TEST>=2020, spread 1.5pip. Riuso simulate_trade di pattern_mining.
"""
from statistics import mean, median
import pattern_mining as pm

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
            if abs(e['price']-sv)/pm.PT_SIZE < 50: continue   # InpMinSLDistPips=5 (=50pt): scarta rischio minuscolo->lotto enorme
            ev.append({'pat':name,'idx':i,'buy':buy,'price':e['price'],
                       'sl_col':sl_col,'tp':tp,'dt':rows[i]['datetime']})
    ev.sort(key=lambda x:x['idx']); return ev

def run_portfolio(rows):
    """1 pos/volta. Ritorna lista trade chiusi con dt, pat, pnl(pt), R(=pnl/rischio), bars, exit.
    R = pnl_pt / distanza-rischio(entry->SL all'apertura): fedele ai SOLDI perche' l'EA
    dimensiona il lotto su quella distanza (ogni SL pieno ~ -1R indipendente dai punti)."""
    trades=[]; last_exit=-1
    for ev in build_events(rows):
        if ev['idx']<=last_exit: continue
        out=pm.simulate_trade(rows,ev['idx'],ev['buy'],ev['price'],ev['sl_col'],ev['tp'],SPREAD)
        if out is None: continue
        pnl,etype,exit_idx,_=out
        sl0=fnum(rows[ev['idx']].get(ev['sl_col']))
        risk_pt=abs(ev['price']-sl0)/pm.PT_SIZE if sl0 else None
        R=(pnl/risk_pt) if (risk_pt and risk_pt>0) else 0.0
        trades.append({'dt':ev['dt'],'pat':ev['pat'],'pnl':pnl,'R':R,
                       'bars':exit_idx-ev['idx'],'exit':etype})
        last_exit=exit_idx
    return trades

def dd_window_R(trades):
    eq=0.0; peak=0.0; mdd=0.0
    for t in trades:
        eq+=t['R']; peak=max(peak,eq); mdd=max(mdd,peak-eq)
    return eq,mdd

def dd_window(trades):
    """Trova indici [i_peak_after, i_trough] della MaxDD sulla curva equity."""
    eq=0.0; peak=0.0; peak_i=-1; mdd=0.0; best=(0,0,0.0,0.0)  # (start_trade_i, trough_i, depth, peak_val)
    for i,t in enumerate(trades):
        eq+=t['pnl']
        if eq>peak: peak=eq; peak_i=i
        dd=peak-eq
        if dd>mdd: mdd=dd; best=(peak_i+1,i,dd,peak)
    return best, mdd

def sec(t): print("\n"+"="*92+"\n  "+t+"\n"+"="*92)

def analyze(label, rows):
    trades=run_portfolio(rows)
    tot=sum(t['pnl'] for t in trades); n=len(trades)
    (start_i,trough_i,depth,peakval),mdd=dd_window(trades)
    sec(f"{label}  |  N={n}  Tot={tot:+.0f}pt  MaxDD={mdd:+.0f}pt  ({tot/mdd:.2f} Ret/DD)")

    # 1) finestra di MaxDD
    win=trades[start_i:trough_i+1]
    if win:
        print(f"\n  [1] FINESTRA MaxDD: dal picco dopo {trades[start_i-1]['dt'] if start_i>0 else 'inizio'} "
              f"al minimo {trades[trough_i]['dt']}  ({len(win)} trade, profondita' {depth:+.0f}pt)")
        wl=[t for t in win if t['pnl']<0]
        print(f"      trade nella finestra: {len(win)} | perdenti {len(wl)} | "
              f"somma perdite {sum(t['pnl'] for t in wl):+.0f}pt | somma vinte {sum(t['pnl'] for t in win if t['pnl']>0):+.0f}pt")
        print(f"      i peggiori 6 della finestra:")
        for t in sorted(win,key=lambda x:x['pnl'])[:6]:
            print(f"        {t['dt']}  {t['pat']}  {t['pnl']:+8.0f}pt  {t['bars']:>3}b  {t['exit']}")

    # 2) attribuzione per pattern
    print(f"\n  [2] PER PATTERN: contributo, perdite, asimmetria")
    print(f"      {'pat':<4} {'N':>4} {'Tot':>8} {'sommaLoss':>10} {'peggiore':>9} {'nLoss':>6} {'winAvg':>7} {'lossAvg':>8}")
    for name,_,_,_,_ in PATTERNS:
        ts=[t for t in trades if t['pat']==name]
        if not ts: continue
        loss=[t['pnl'] for t in ts if t['pnl']<0]; win_=[t['pnl'] for t in ts if t['pnl']>0]
        print(f"      {name:<4} {len(ts):>4} {sum(t['pnl'] for t in ts):>+8.0f} "
              f"{sum(loss):>+10.0f} {(min(loss) if loss else 0):>+9.0f} {len(loss):>6} "
              f"{(mean(win_) if win_ else 0):>+7.0f} {(mean(loss) if loss else 0):>+8.0f}")

    # 3) concentrazione: quanta parte delle perdite dai top-K trade
    losses=sorted([t for t in trades if t['pnl']<0],key=lambda x:x['pnl'])
    tot_loss=sum(t['pnl'] for t in losses)
    print(f"\n  [3] CONCENTRAZIONE PERDITE (perdite totali {tot_loss:+.0f}pt su {len(losses)} trade in perdita)")
    for K in (3,5,10):
        if len(losses)>=K:
            share=sum(t['pnl'] for t in losses[:K])/tot_loss*100
            print(f"      top-{K:>2} perdite = {sum(t['pnl'] for t in losses[:K]):+.0f}pt = {share:.0f}% di tutte le perdite")
    print(f"      le 8 perdite peggiori in assoluto:")
    for t in losses[:8]:
        print(f"        {t['dt']}  {t['pat']}  {t['pnl']:+8.0f}pt  {t['bars']:>3}b  {t['exit']}")

    # 4) exit mix
    from collections import Counter
    c=Counter(t['exit'] for t in trades)
    csum={k:sum(t['pnl'] for t in trades if t['exit']==k) for k in c}
    print(f"\n  [4] USCITE: "+" | ".join(f"{k} N{c[k]} tot{csum[k]:+.0f}" for k in c))

    # 5) VISTA SOLDI (unita' di rischio R): questa e' la verita' col sizing dell'EA
    totR,mddR=dd_window_R(trades)
    winsR=[t['R'] for t in trades if t['R']>0]; lossR=[t['R'] for t in trades if t['R']<0]
    print(f"\n  [5] IN UNITA' DI RISCHIO (R, fedele ai soldi con sizing rischio):")
    print(f"      Tot {totR:+.1f}R | MaxDD {mddR:+.1f}R | Ret/DD {totR/mddR:.2f} | "
          f"win medio {mean(winsR):+.2f}R | loss medio {(mean(lossR) if lossR else 0):+.2f}R")
    be = abs(mean(lossR))/(mean(winsR)+abs(mean(lossR)))*100 if winsR and lossR else 0
    wr = len(winsR)/len(trades)*100
    print(f"      -> a RiskPct=12%: MaxDD ~ {mddR*12:.0f}% equity (grezzo, no compounding)")
    print(f"      -> win% reale {wr:.1f}% vs break-even {be:.1f}%  (margine {wr-be:+.1f} punti = quanto e' sottile l'edge)")
    worstR=sorted(trades,key=lambda x:x['R'])[:6]
    print(f"      6 perdite peggiori in R: "+" ".join(f"{t['pat']}:{t['R']:+.2f}" for t in worstR))

def main():
    rows=pm.load_csv(CSV)
    tr=[r for r in rows if r['datetime']<SPLIT]; te=[r for r in rows if r['datetime']>=SPLIT]
    print(f"EURUSD {rows[0]['datetime']}->{rows[-1]['datetime']} | train {len(tr)} / test {len(te)} barre | 1 pos/volta")
    analyze("TRAIN", tr); analyze("TEST", te)
    print("\nLettura: se le perdite sono CONCENTRATE (top-5 = gran parte del DD) e su SL lontani,")
    print("la leva e' un CAP sulla distanza SL o size ridotta quando MA365 e' lontana - non l'entry.")

if __name__=="__main__": main()
