#!/usr/bin/env python3
"""
squeeze2.py - Re-test squeeze con misura PULITA: range recente basso (quiete vera),
non l'ampiezza del ventaglio MA (che si confonde col trend). Stessa meccanica breakout.
Domanda: dopo un periodo di range COMPRESSO, il breakout e' tradabile e batte i breakout normali?
"""
from statistics import mean
import pattern_mining as pm
rows=pm.load_csv("../EURUSD/PAPP_Export.csv"); n=len(rows); PT=pm.PT_SIZE
SPLIT="2020.01.01"; SPREAD=15
def gf(i,c):
    try: return float(rows[i][c])
    except: return None
hi=[gf(i,'high') for i in range(n)]; lo=[gf(i,'low') for i in range(n)]; cl=[gf(i,'close') for i in range(n)]
dts=[rows[i]['datetime'] for i in range(n)]
# range recente (ATR-like) su 10 barre, percentile rolling 252
RR=[None]*n
for i in range(10,n):
    rs=[hi[j]-lo[j] for j in range(i-9,i+1) if hi[j] and lo[j]]
    if len(rs)==10: RR[i]=mean(rs)
rrpct=[None]*n
for i in range(n):
    if RR[i] is None: continue
    h=[RR[j] for j in range(max(0,i-252),i) if RR[j] is not None]
    if len(h)<60: continue
    rrpct[i]=sum(1 for x in h if x<RR[i])/len(h)
def fwd_range(i,h):
    js=[j for j in range(i+1,min(i+h+1,n)) if hi[j] and lo[j]]
    return (max(hi[j] for j in js)-min(lo[j] for j in js))/PT if js else None
print("=== Parte A2: range recente BASSO predice espansione? (range futuro pt, h=10) ===")
for lbl,dd in (("TRAIN",lambda d:d<SPLIT),("TEST",lambda d:d>=SPLIT)):
    bins={0:[],4:[]}
    for i in range(n):
        if rrpct[i] is None or not dd(dts[i]): continue
        fr=fwd_range(i,10)
        if fr is None: continue
        if rrpct[i]<0.2: bins[0].append(fr)
        elif rrpct[i]>=0.8: bins[4].append(fr)
    print(f"  {lbl}: quiete(rr<0.2)={mean(bins[0]):.0f} (N{len(bins[0])})  agitato(rr>0.8)={mean(bins[4]):.0f} (N{len(bins[4])})")
# breakout
K=10;WAIT=12;MAXH=40
def box(i):
    js=[j for j in range(max(0,i-K+1),i+1) if hi[j] and lo[j]]
    return (max(hi[j] for j in js),min(lo[j] for j in js)) if len(js)>=K else None
def run(sig):
    trades=[];i=K;block=-1
    while i<n-2:
        if i<=block or rrpct[i] is None or not sig(i): i+=1;continue
        bx=box(i)
        if not bx:i+=1;continue
        bh,bl=bx;ent=False
        for j in range(i+1,min(i+WAIT+1,n)):
            if hi[j] is None:continue
            buy=hi[j]>=bh;sell=lo[j]<=bl
            if buy or sell:
                d=1 if(buy and not sell)else(-1 if(sell and not buy)else(1 if cl[j]>=cl[j-1]else -1))
                entry=bh if d==1 else bl;stop=bl if d==1 else bh;pnl=None
                for k in range(j,min(j+MAXH,n)):
                    if hi[k] is None:continue
                    if d==1 and lo[k]<=stop:pnl=(stop-entry)/PT-SPREAD;end=k;break
                    if d==-1 and hi[k]>=stop:pnl=(entry-stop)/PT-SPREAD;end=k;break
                    m30=gf(k,'MA30')
                    if m30:
                        if d==1 and cl[k]<m30:pnl=(cl[k]-entry)/PT-SPREAD;end=k;break
                        if d==-1 and cl[k]>m30:pnl=(entry-cl[k])/PT-SPREAD;end=k;break
                else:end=min(j+MAXH,n-1);pnl=(cl[end]-entry)/PT*d-SPREAD
                if pnl is None:end=min(j+MAXH,n-1);pnl=(cl[end]-entry)/PT*d-SPREAD
                trades.append((i,pnl));block=end;ent=True;i=end;break
        if not ent:i+=1
    return trades
def stats(ts):
    if len(ts)<5:return None
    p=[x[1]for x in ts];tot=sum(p);g=sum(x for x in p if x>0);l=-sum(x for x in p if x<0)
    return len(p),tot,tot/len(p),(g/l if l>0 else 9.9),sum(1 for x in p if x>0)/len(p)*100
print("\n=== Parte B2: breakout dopo QUIETE vera vs normale ===")
for lbl,sig in (("QUIETE (rr_pct<0.2)",lambda i:rrpct[i]<0.2),("NORMALE (0.4-0.6) [null]",lambda i:0.4<=rrpct[i]<0.6)):
    ts=run(sig);tr=[t for t in ts if dts[t[0]]<SPLIT];te=[t for t in ts if dts[t[0]]>=SPLIT]
    print(f"\n  {lbl}")
    for s,st in(("TUTTO",stats(ts)),("TRAIN",stats(tr)),("TEST",stats(te))):
        if st:print(f"    {s:6s} N={st[0]:3d} tot={st[1]:+6.0f} EV={st[2]:+5.0f} PF={st[3]:.2f} win={st[4]:3.0f}%")
