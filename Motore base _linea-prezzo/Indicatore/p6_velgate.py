#!/usr/bin/env python3
"""
p6_velgate.py - CONFERMA sui 6 pattern VERI del motore base EURUSD (file nuovo,
non tocca l'EA ne' gli altri tool).

Domanda (dal ragionamento linea+prezzo+features): il gate "velocita' concorde"
che regge train+test sul pool linea-linea (line_feat_combo.py), regge anche sui
6 pattern che l'EA trada davvero (P1-P6, cross prezzo-linea, direzione fissa)?

Metodo:
- P1-P6 esatti come EA_EURUSD.mq5 (entry line, dir, SL line, TP pip).
- Entrata = cross prezzo-linea nel verso del pattern (detect_entries di pattern_mining).
- Uscita = SL dinamico sulla linea + TP fisso (simulate_trade), stesso motore
  usato da pattern_mining -> nessuna nuova simulazione da fidarsi.
- Split temporale TRAIN < 2020 / TEST >= 2020.
- Gate a confronto (tutti calcolabili live dall'EA salvo cluPct, vedi note):
    G0    baseline (nessun gate)
    Gvel  segno velocita' (vel%) concorde con la direzione del trade
    Gfrat segno spread frattale (fastAvg-slowAvg) concorde
    Gclu  cluPct sopra la mediana-train (fascio non in compressione estrema)
    Gvf   Gvel AND Gfrat
- Due viste: (1) per-pattern EV/win/N; (2) PORTAFOGLIO dei 6 insieme, 1 posizione
  per volta -> misura MaxDD e Ret/DD reali (la metrica che conta per l'EA).

NB scientifico: Gvel/Gfrat sono decisi PRIMA di vedere i risultati (dal pool),
quindi qui NON stiamo ri-ottimizzando: e' un test di conferma out-of-family.
"""
import sys
from statistics import mean, median
import pattern_mining as pm

CSV   = "../EURUSD/PAPP_Export.csv"
SPLIT = "2020.01.01"
SPREAD = 15   # 1.5 pip round-trip, come i default del progetto

# P1-P6 esatti da EA_EURUSD.mq5 (entry, dir 1=BUY/-1=SELL, SL line, TP pip)
PATTERNS = [
    ("P1", "MA30",  -1, "MA365", 15),
    ("P2", "MA121",  1, "MA365", 15),
    ("P3", "MA365", -1, "MA121", 12),
    ("P4", "MA7",   -1, "MA365", 12),
    ("P5", "MA30",   1, "MA365", 15),
    ("P6", "MA14",   1, "MA365", 15),
]

def fnum(x):
    try: return float(x)
    except: return None

def build_events(rows):
    """Tutte le entrate P1-P6 come dict: idx, buy, price, sl_col, tp, dt, + feature d'ingresso.
    Scarta le entrate con SL dal lato sbagliato, ESATTAMENTE come l'EA (R|skip_slunplace)
    e come analyze_dynamic_sl_grid: SELL richiede SL sopra l'entry, BUY sotto."""
    ents = pm.detect_entries(rows)                       # cross prezzo-linea
    idx_by = {}                                          # (line,dir) -> lista entries
    for e in ents:
        idx_by.setdefault((e['line'], e['dir']), []).append(e)
    events = []
    for name, entry, d, sl, tp in PATTERNS:
        sl_col = pm.LINE_COLS[pm.LINE_NAMES.index(sl)]
        buy = (d == 1)
        for e in idx_by.get((entry, d), []):
            i = e['idx']; r = rows[i]
            sl_val = fnum(r.get(sl_col))
            if sl_val is None or not (0 < sl_val < 1e12):        continue
            if buy and sl_val >= e['price']:                     continue   # SL non piazzabile sotto
            if (not buy) and sl_val <= e['price']:               continue   # SL non piazzabile sopra
            events.append({
                'pat': name, 'idx': i, 'buy': (d == 1), 'dir': d,
                'price': e['price'], 'sl_col': sl_col, 'tp': tp, 'dt': r['datetime'],
                'vel': fnum(r.get('vel%')), 'frat': fnum(r.get('spread')),
                'cluPct': fnum(r.get('cluPct')),
            })
    events.sort(key=lambda x: x['idx'])
    return events

def pnl_of(rows, ev):
    out = pm.simulate_trade(rows, ev['idx'], ev['buy'], ev['price'],
                            ev['sl_col'], ev['tp'], SPREAD)
    return out[0] if out else None

# ---- gate: ritornano True se l'entrata passa il filtro ----
def g0(ev, clu_thr):   return True
def gvel(ev, clu_thr): return ev['vel']  is not None and ((ev['vel']  > 0) == (ev['dir'] > 0))
def gfrat(ev, clu_thr):return ev['frat'] is not None and ((ev['frat'] > 0) == (ev['dir'] > 0))
def gclu(ev, clu_thr): return ev['cluPct'] is not None and ev['cluPct'] > clu_thr
def gvf(ev, clu_thr):  return gvel(ev, clu_thr) and gfrat(ev, clu_thr)

GATES = [("G0 base", g0), ("Gvel", gvel), ("Gfrat", gfrat), ("Gclu", gclu), ("Gvf vel+frat", gvf)]

def per_trade_stats(pnls):
    if not pnls: return None
    n = len(pnls); tot = sum(pnls); win = sum(1 for p in pnls if p > 0)/n*100
    return n, tot, tot/n, win

def portfolio(rows, events, gate, clu_thr):
    """1 posizione per volta (capitale unico): misura MaxDD e Ret/DD reali."""
    eq = 0.0; peak = 0.0; mdd = 0.0; last_exit = -1
    pnls = []
    for ev in events:
        if not gate(ev, clu_thr): continue
        if ev['idx'] <= last_exit: continue          # posizione gia' aperta
        out = pm.simulate_trade(rows, ev['idx'], ev['buy'], ev['price'],
                                ev['sl_col'], ev['tp'], SPREAD)
        if out is None: continue
        pnl, _etype, exit_idx, _ = out
        pnls.append(pnl); eq += pnl
        peak = max(peak, eq); mdd = max(mdd, peak - eq)
        last_exit = exit_idx
    if not pnls: return None
    n = len(pnls); tot = eq; win = sum(1 for p in pnls if p > 0)/n*100
    pf_num = sum(p for p in pnls if p > 0); pf_den = abs(sum(p for p in pnls if p < 0))
    pf = pf_num/pf_den if pf_den > 0 else float('inf')
    retdd = tot/mdd if mdd > 0 else float('inf')
    return {'n': n, 'tot': tot, 'win': win, 'pf': pf, 'mdd': mdd, 'retdd': retdd}

def main():
    rows = pm.load_csv(CSV)
    train = [r for r in rows if r['datetime'] <  SPLIT]
    test  = [r for r in rows if r['datetime'] >= SPLIT]
    print(f"EURUSD {rows[0]['datetime']} -> {rows[-1]['datetime']} | "
          f"train {len(train)} barre / test {len(test)} barre | split {SPLIT} | spread {SPREAD/10:.1f}pip\n")

    # soglia cluPct = mediana calcolata SOLO su train (niente look-ahead)
    ev_tr_all = build_events(train)
    clu_vals = [e['cluPct'] for e in ev_tr_all if e['cluPct'] is not None]
    clu_thr = median(clu_vals) if clu_vals else 0.0
    print(f"soglia Gclu (mediana cluPct train) = {clu_thr:.3f}\n")

    ev_tr = build_events(train)
    ev_te = build_events(test)

    # ---------- VISTA 1: per pattern, EV per trade (indipendente, no portafoglio) ----------
    print("="*96)
    print("VISTA 1 — per pattern: EV(pt/trade) win% N   [ TRAIN | TEST ]   effetto del gate velocita'")
    print("="*96)
    print(f"  {'pat':<4} {'gate':<12}  {'TRAIN EV':>8} {'win':>5} {'N':>5}   {'TEST EV':>8} {'win':>5} {'N':>5}")
    print("-"*96)
    for name, entry, d, sl, tp in PATTERNS:
        for glbl, gfn in (("G0 base", g0), ("Gvel", gvel)):   # per-pattern mostro solo base vs vel
            tr = per_trade_stats([pnl_of(train, e) for e in ev_tr if e['pat']==name and gfn(e, clu_thr)
                                  and pnl_of(train, e) is not None])
            te = per_trade_stats([pnl_of(test,  e) for e in ev_te if e['pat']==name and gfn(e, clu_thr)
                                  and pnl_of(test,  e) is not None])
            def fmt(s): return f"{s[2]:>+8.0f} {s[3]:>4.0f}% {s[0]:>5}" if s else f"{'n/a':>8} {'':>5} {'':>5}"
            tag = f"{entry} {'BUY' if d==1 else 'SELL'}"
            print(f"  {name:<4} {glbl:<12}  {fmt(tr)}   {fmt(te)}   {tag if glbl=='G0 base' else ''}")
        print()

    # ---------- VISTA 2: PORTAFOGLIO dei 6 pattern insieme (il vero motore base) ----------
    print("="*96)
    print("VISTA 2 — PORTAFOGLIO P1-P6 (1 posizione/volta): la metrica che conta per l'EA")
    print("="*96)
    for label, subset in (("TRAIN", train), ("TEST", test)):
        evs = build_events(subset)
        print(f"\n  [{label}]  {'gate':<13} {'N':>5} {'TotPt':>9} {'Win%':>6} {'PF':>6} {'MaxDD':>8} {'Ret/DD':>7}")
        print("  " + "-"*70)
        base = None
        for glbl, gfn in GATES:
            m = portfolio(subset, evs, gfn, clu_thr)
            if m is None:
                print(f"  {'':13} {glbl:<13}  [nessun trade]"); continue
            if glbl == "G0 base": base = m
            rd = f"{m['retdd']:>7.2f}" if m['retdd'] != float('inf') else "    inf"
            delta = ""
            if base and glbl != "G0 base":
                dd_ret = (m['retdd']-base['retdd']) if base['retdd']!=float('inf') else 0
                delta = f"  ΔRet/DD {dd_ret:+.2f}"
            print(f"  {'':13} {glbl:<13} {m['n']:>5} {m['tot']:>+9.0f} {m['win']:>5.0f}% "
                  f"{m['pf']:>6.2f} {m['mdd']:>8.0f} {rd}{delta}")

    print("\nLettura: se Gvel alza Ret/DD e PF su TRAIN *e* TEST tenendo N ragionevole,")
    print("il gate velocita' e' confermato out-of-family -> integrabile nell'EA come")
    print("check sul segno di BUF_VEL prima di TrySendEntry. Se peggiora il test, stop.")

if __name__ == "__main__":
    main()
