#!/usr/bin/env python3
"""
Pattern Mining per PaPP Median v3 - CORRETTO
- Crossover calcolati su D1 reali (non interpolati)
- SL dinamico: prezzo tocca la linea (segue il movimento)
- Spread/commissioni configurabili
- Walk-forward: training set + test set separati
- Sharpe ratio: std=0 gestito correttamente
- Filtri contestuali attivi
- Analisi a PORTAFOGLIO: equity sequenziale, 1 posizione/volta (no trade
  sovrapposti), max drawdown, Ret/DD ed exposure reali
- Selezione ROBUSTA: tiene solo i pattern profittevoli su train E test
  (Sharpe penalizzato per numero trade), per difendersi dall'overfitting

Uso: python3 pattern_mining.py <PAPP_Export.csv> [opzioni]

Opzioni:
  --output=NOME       Salva output completo su file (default: solo stdout)
  --spread=N          Spread in punti (default: 15 = 1.5 pip EURUSD)
  --commission=N      Commissione round-trip in punti (default: 0; es. 7 = 0.7 pip)
  --swap=N            Swap in punti per barra D1 tenuta (default: 0; puo' essere negativo)
  --train-pct=N       Percentuale per training (default: 1.0 = 100%)
  --split-date=YYYY.MM.DD  Cutoff train/test (sovrascrive train-pct)
  --min-trades=N      Minimo trade per pattern valido (default: 10)
  Filtri:
    min_cluster=N  max_cluster=N
    min_vel=N      max_vel=N
    min_vol=N      max_vol=N
    min_orderScore=N  max_orderScore=N
    min_spread=N   max_spread=N
    min_dMed=N     max_dMed=N
    longBelow=1    longAbove=1

Esempi:
  python3 pattern_mining.py PAPP_Export.csv --spread=15 --train-pct=0.7
  python3 pattern_mining.py PAPP_Export.csv --spread=20 --split-date=2020.01.01
  python3 pattern_mining.py PAPP_Export.csv --spread=10 min_orderScore=2 longAbove=1
"""
import csv, sys, os
from collections import defaultdict
from statistics import mean, stdev, median
from math import sqrt

class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

PT_SIZE  = 0.00001
PIP_SIZE = 10 * PT_SIZE      # 1 pip = 10 punti (simboli a 5 decimali)
MAX_BARS = 200

LINE_NAMES = ['MA365', 'MA182', 'MA121', 'MA30', 'MA14', 'MA7', 'MA3', 'Median']
LINE_COLS  = ['MA365', 'MA182', 'MA121', 'MA30', 'MA14', 'MA7', 'MA3', 'median']
CROSS_COLS = ['crossMA365', 'crossMA182', 'crossMA121', 'crossMA30',
              'crossMA14', 'crossMA7', 'crossMA3', 'crossMed']
ABOVE_COLS = ['a365', 'a182', 'a121', 'a30', 'a14', 'a7', 'a3', 'aMed']

# Colonne booleane "linea sopra linea" (1 = prima > seconda). Un FLIP tra due
# barre D1 consecutive e' un crossover LINEA-LINEA (le medie si intersecano):
#   0->1 = veloce incrocia SOPRA la lenta (bullish, dir=+1)
#   1->0 = veloce incrocia SOTTO la lenta (bearish, dir=-1)
PAIR_COLS = ['MA3_7', 'MA7_14', 'MA14_30', 'MA30_121', 'MA121_182', 'MA182_365']

SL_CANDIDATES = ['MA14', 'MA30', 'MA121', 'MA365', 'Median']
TP_CANDIDATES = [2, 3, 4, 5, 6, 8, 10, 12, 15]   # in PIP (come gli input EA)

# ============================================================
def load_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))

def entry_context(row):
    return {
        'cluster': float(row['cluster%']),
        'vel':     float(row['vel%']),
        'acc':     float(row['acc%']),
        'vol':     float(row['vol%']),
        'orderScore': int(row['orderScore']),
        'spread':  float(row['spread']),
        'spreadVel': float(row['spreadVel']),
        'longBelow': int(row['longBelow']),
        'longAbove': int(row['longAbove']),
        'dMed':    float(row['dMed%']),
    }

def detect_entries(rows, include_line_cross=False):
    entries = []
    # --- Crossover PREZZO-linea (close incrocia una MA) ---
    for i, row in enumerate(rows):
        for line_name, cross_col in zip(LINE_NAMES, CROSS_COLS):
            cross_val = int(row.get(cross_col, 0))
            if cross_val == 0:
                continue
            entries.append({
                'idx': i,
                'line': line_name,
                'dir': cross_val,
                'price': float(row['close']),
                'datetime': row['datetime'],
                'ctx': entry_context(row),
            })
    # --- Crossover LINEA-linea (due MA si intersecano tra loro) ---
    if include_line_cross:
        for i in range(1, len(rows)):
            for col in PAIR_COLS:
                try:
                    cur = int(rows[i][col]); prev = int(rows[i-1][col])
                except (ValueError, KeyError):
                    continue
                if cur == prev:
                    continue
                entries.append({
                    'idx': i,
                    'line': 'X' + col,             # es. 'XMA3_7'
                    'dir': 1 if (prev == 0 and cur == 1) else -1,
                    'price': float(rows[i]['close']),
                    'datetime': rows[i]['datetime'],
                    'ctx': entry_context(rows[i]),
                })
    return entries

# ============================================================
# SHARPE CORRETTO: gestisce std=0
# ============================================================
def compute_sharpe(pnls):
    # Sharpe PER-TRADE (avg/sd). NON annualizzato con sqrt(252): i trade
    # sono eventi sporadici (~pochi/anno); moltiplicare per sqrt(252)
    # assumeva 252 trade/anno e gonfiava il valore di ~10-15x.
    # Per annualizzare: moltiplicare per sqrt(trade_per_anno).
    if len(pnls) < 2:
        return 0.0
    avg = mean(pnls)
    try:
        sd = stdev(pnls)
    except:
        sd = 0
    # Varianza nulla O quasi-nulla (CV < 10%) = artefatto, non un edge reale.
    # Tipico dei pattern dominati da un TP fisso: quasi tutti i trade chiudono
    # allo stesso valore -> pnl pressoche' identici -> sd minuscola -> Sharpe
    # esplode (visti 400+, fisicamente impossibili per trade con uscite varie).
    # Un edge vero ha forte dispersione trade-su-trade (coeff. di variazione
    # ben oltre il 10%). Sotto soglia azzeriamo per non inquinare la classifica.
    if sd == 0 or (avg != 0 and sd < 0.10 * abs(avg)):
        return 0.0
    return avg / sd

# ============================================================
# SIMULAZIONE TRADE: SL DINAMICO sulla linea, TP fisso
# ============================================================
def simulate_trade(rows, entry_idx, buy, entry_price, sl_col, tp_pt,
                   spread_pt=0, commission_pt=0, swap_pt=0, max_bars=MAX_BARS):
    end = min(entry_idx + max_bars, len(rows))
    for j in range(entry_idx+1, end):
        row = rows[j]
        hi = float(row['high'])
        lo = float(row['low'])
        # SL = valore della linea alla barra PRECEDENTE (j-1), noto a inizio
        # barra j: niente look-ahead. (Prima usava row[j], cioe' la MA
        # calcolata con la chiusura della stessa barra di cui si testa il low.)
        sl_val = float(rows[j-1][sl_col])
        bars = j - entry_idx
        cost = spread_pt + commission_pt + swap_pt * bars

        # SL DINAMICO: il prezzo tocca la linea
        if buy and lo <= sl_val:
            pnl = (sl_val - entry_price) / PT_SIZE - cost
            return pnl, 'SL', j, sl_col
        if not buy and hi >= sl_val:
            pnl = (entry_price - sl_val) / PT_SIZE - cost
            return pnl, 'SL', j, sl_col

        # TP fisso (tp_pt in PIP; il livello usa PIP_SIZE, il PnL resta in punti = tp_pt*10)
        if buy and hi >= entry_price + tp_pt * PIP_SIZE:
            return tp_pt*10 - cost, 'TP', j, 'TP'
        if not buy and lo <= entry_price - tp_pt * PIP_SIZE:
            return tp_pt*10 - cost, 'TP', j, 'TP'

    # TIMEOUT: ne' SL ne' TP entro max_bars -> chiudi mark-to-market
    # all'ultima close disponibile (NON scartare: scartare nascondeva i
    # trade-zombie e creava censoring bias).
    j = end - 1
    if j > entry_idx:
        close_j = float(rows[j]['close'])
        bars = j - entry_idx
        cost = spread_pt + commission_pt + swap_pt * bars
        pnl = ((close_j - entry_price) if buy else (entry_price - close_j)) / PT_SIZE - cost
        return pnl, 'TIMEOUT', j, 'TIMEOUT'
    return None

# ============================================================
# USCITA SU CROSSOVER DI LINEA SPECIFICA (in direzione opposta)
# ============================================================
def simulate_exit_on_cross(rows, entry_idx, buy, exit_cross_col,
                           commission_pt=0, swap_pt=0, max_bars=MAX_BARS):
    # NB: lo spread viene sottratto dai chiamanti; qui aggiungiamo
    # commissione (una volta) e swap (per barra tenuta).
    entry_price = float(rows[entry_idx]['close'])
    for j in range(entry_idx+1, min(entry_idx+max_bars, len(rows))):
        row = rows[j]
        close_j = float(row['close'])
        cv = int(row.get(exit_cross_col, 0))
        if cv == 0:
            continue
        bars = j - entry_idx
        cost = commission_pt + swap_pt * bars
        if buy and cv == -1:
            return (close_j - entry_price) / PT_SIZE - cost, 'CROSS', j, exit_cross_col
        if not buy and cv == 1:
            return (entry_price - close_j) / PT_SIZE - cost, 'CROSS', j, exit_cross_col
    return None

# ============================================================
# ANALISI 1: Entry su crossover → exit su prossimo crossover opposto (qualsiasi linea)
# ============================================================
def analyze_cross_to_opposite(entries, rows, spread_pt=0, commission_pt=0, swap_pt=0):
    results = []
    for ent in entries:
        buy = (ent['dir'] == 1)
        entry_price = ent['price']
        idx = ent['idx']
        for j in range(idx+1, min(idx+MAX_BARS, len(rows))):
            row = rows[j]
            close_j = float(row['close'])
            cost = spread_pt + commission_pt + swap_pt * (j - idx)
            hit = False
            for cross_col in CROSS_COLS:
                cv = int(row.get(cross_col, 0))
                if cv == 0:
                    continue
                if buy and cv == -1:
                    pnl = (close_j - entry_price) / PT_SIZE - cost
                    results.append({**ent, 'exit_line': cross_col, 'exit_type': 'OPP_CROSS',
                                    'bars_held': j-idx, 'pnl_pt': pnl, 'exit_idx': j})
                    hit = True
                    break
                if not buy and cv == 1:
                    pnl = (entry_price - close_j) / PT_SIZE - cost
                    results.append({**ent, 'exit_line': cross_col, 'exit_type': 'OPP_CROSS',
                                    'bars_held': j-idx, 'pnl_pt': pnl, 'exit_idx': j})
                    hit = True
                    break
            if hit:
                break
    return results

# ============================================================
# ANALISI 2: Entry su crossover → exit su crossover di linea specifica
# ============================================================
def analyze_cross_to_specific(entries, rows, spread_pt=0, commission_pt=0, swap_pt=0):
    results = []
    for ent in entries:
        buy = (ent['dir'] == 1)
        for exit_cross_col in CROSS_COLS:
            ex = simulate_exit_on_cross(rows, ent['idx'], buy, exit_cross_col,
                                        commission_pt, swap_pt)
            if ex is None:
                continue
            pnl, etype, eidx, eline = ex
            pnl -= spread_pt
            results.append({**ent, 'exit_line': eline, 'exit_type': 'SPEC_CROSS',
                            'bars_held': eidx - ent['idx'], 'pnl_pt': pnl, 'exit_idx': eidx})
    return results

# ============================================================
# ANALISI 3: Grid search - SL dinamico su linea + TP fisso
# ============================================================
def analyze_dynamic_sl_grid(entries, rows, spread_pt=0, commission_pt=0, swap_pt=0):
    results = []
    for ent in entries:
        buy = (ent['dir'] == 1)
        entry_price = ent['price']
        idx = ent['idx']

        for sl_name in SL_CANDIDATES:
            sl_col = LINE_COLS[LINE_NAMES.index(sl_name)]
            sl_val = float(rows[idx][sl_col])
            if not (sl_val > 0 and sl_val < 1e12):
                continue
            # Verifica che lo SL sia dalla parte giusta
            if buy and sl_val >= entry_price:
                continue
            if not buy and sl_val <= entry_price:
                continue

            for tp_pt in TP_CANDIDATES:
                outcome = simulate_trade(rows, idx, buy, entry_price,
                                         sl_col, tp_pt, spread_pt,
                                         commission_pt, swap_pt)
                if outcome is None:
                    continue
                pnl, exit_type, exit_idx, exit_line = outcome
                sl_name_used = sl_name if exit_type == 'SL' else exit_line
                results.append({**ent, 'exit_line': sl_name_used, 'exit_type': exit_type,
                                'bars_held': exit_idx - idx, 'pnl_pt': pnl, 'exit_idx': exit_idx,
                                'sl_line': sl_name, 'tp_pt': tp_pt})
    return results

# ============================================================
# APPLICA FILTRI CONTESTUALI
# ============================================================
def apply_context_filters(entries, ctx_filters):
    filtered = []
    for e in entries:
        ctx = e['ctx']
        ok = True
        for k, v in ctx_filters.items():
            if k.startswith('min_'):
                key = k[4:]
                if key in ctx and ctx[key] < v:
                    ok = False
                    break
            elif k.startswith('max_'):
                key = k[4:]
                if key in ctx and ctx[key] > v:
                    ok = False
                    break
            elif k == 'longBelow' and ctx.get('longBelow', 0) != v:
                ok = False
                break
            elif k == 'longAbove' and ctx.get('longAbove', 0) != v:
                ok = False
                break
        if ok:
            filtered.append(e)
    return filtered

# ============================================================
# SPLIT TRAIN/TEST
# ============================================================
def split_train_test(rows, train_pct=1.0, split_date=None):
    if train_pct >= 1.0 and split_date is None:
        return rows, []
    if split_date:
        cutoff = split_date
    else:
        cutoff = rows[0]['datetime'] if train_pct < 1.0 else None
        if cutoff:
            total = len(rows)
            cutoff_idx = int(total * train_pct)
            cutoff = rows[cutoff_idx]['datetime']
    train = [r for r in rows if r['datetime'] < cutoff]
    test  = [r for r in rows if r['datetime'] >= cutoff]
    return train, test

# ============================================================
# AGGREGAZIONE + CLASSIFICA
# ============================================================
def aggregate(results, group_keys, min_trades=5):
    groups = defaultdict(list)
    for r in results:
        key = tuple(r.get(k, '?') for k in group_keys)
        groups[key].append(r)

    agg = []
    for key, trades in groups.items():
        pnls = [t['pnl_pt'] for t in trades]
        if len(pnls) < min_trades:
            continue
        wins = sum(1 for p in pnls if p > 0)
        wr = wins / len(pnls) * 100
        ap = mean(pnls)
        sh = compute_sharpe(pnls)
        pf = sum(p for p in pnls if p > 0) / max(1, abs(sum(p for p in pnls if p < 0)))
        agg.append({
            'key': key,
            'trades': len(pnls),
            'win_rate': wr,
            'avg_pnl': ap,
            'sharpe': sh,
            'profit_factor': pf,
            'total_pnl': sum(pnls),
            'avg_bars': mean(t['bars_held'] for t in trades),
        })
    return sorted(agg, key=lambda x: -x['sharpe'])

# ============================================================
# STAMPA
# ============================================================
def print_table(patterns, headers, title, top=30):
    if not patterns:
        print(f"\n  [nessun pattern]")
        return
    print(f"\n{'='*140}")
    print(f"  {title}")
    print(f"{'='*140}")
    hline = '  '.join(f"{h:<14}" for h in headers)
    print(f"{hline}  {'Trades':>7} {'Win%':>7} {'AvgPts':>9} {'Sharpe':>8} {'ProfitF':>9} {'TotPnl':>10} {'AvgBars':>7}")
    print('-')
    for p in patterns[:top]:
        vals = '  '.join(f"{str(k):<14}" for k in p['key'])
        print(f"{vals}  {p['trades']:>7} {p['win_rate']:>6.1f}% {p['avg_pnl']:>+9.1f} {p['sharpe']:>8.2f} {p['profit_factor']:>9.2f} {p['total_pnl']:>+10.0f} {p['avg_bars']:>7.1f}")

def print_section(title):
    print(f"\n{'='*140}")
    print(f"  {title}")
    print(f"{'='*140}")

# ============================================================
# RIEPILOGO FINALE
# ============================================================
def print_summary(all_results, min_trades=10):
    print_section("RIEPILOGO: Miglior pattern per ogni linea di entrata")

    by_entry = defaultdict(list)
    for r in all_results:
        by_entry[r['line']].append(r)

    for line in LINE_NAMES:
        trades = by_entry.get(line, [])
        if len(trades) < min_trades:
            continue

        # Raggruppa per (dir, exit_line, exit_type, tp_pt, sl_line)
        groups = defaultdict(list)
        for t in trades:
            k = (t['dir'], t.get('exit_line', '?'), t.get('exit_type', '?'),
                 t.get('tp_pt', 0), t.get('sl_line', ''))
            groups[k].append(t)

        best = None
        best_sh = -999
        for key, ts in groups.items():
            pnls = [t['pnl_pt'] for t in ts]
            if len(pnls) < min_trades:
                continue
            sh = compute_sharpe(pnls)
            if sh > best_sh:
                wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100
                best = (key, len(pnls), wr, mean(pnls), sh)
                best_sh = sh

        if best:
            (d, ex, etype, tp, sl), n, wr, avg, sh = best
            d_str = 'BUY' if d == 1 else 'SELL'
            extra = f" TP={tp}pip" if tp else ""
            extra += f" SL={sl}" if sl else ""
            extra += f" [{etype}]" if etype else ""
            print(f"  {line:<10} -> {d_str:<5} | exit={ex:<10}{extra:<25} | "
                  f"Sharpe={sh:>6.2f} | Win={wr:>5.0f}% | Avg={avg:>+7.1f}pt | N={n:>5}")

# ============================================================
# EXIT su prossimo crossover OPPOSTO (qualsiasi linea) -> (pnl, exit_idx)
# ============================================================
def exit_opposite_cross(rows, entry_idx, buy, spread_pt=0, commission_pt=0,
                        swap_pt=0, max_bars=MAX_BARS):
    entry_price = float(rows[entry_idx]['close'])
    for j in range(entry_idx+1, min(entry_idx+max_bars, len(rows))):
        row = rows[j]
        close_j = float(row['close'])
        cost = spread_pt + commission_pt + swap_pt * (j - entry_idx)
        for cc in CROSS_COLS:
            cv = int(row.get(cc, 0))
            if cv == 0:
                continue
            if buy and cv == -1:
                return (close_j - entry_price) / PT_SIZE - cost, j
            if not buy and cv == 1:
                return (entry_price - close_j) / PT_SIZE - cost, j
    return None

# ============================================================
# REGOLA di pattern come INPUT (non outcome). Tipi:
#   GRID: {type, line, dir, sl, tp}   -> SL dinamico su linea + TP fisso
#   SPEC: {type, line, dir, exit_col} -> uscita su crossover linea specifica
#   OPP:  {type, line, dir}           -> uscita su primo crossover opposto
# make_exit_fn ritorna fn(ent) -> (pnl_pt, exit_idx) | None
# ============================================================
def make_exit_fn(rows, rule, spread_pt=0, commission_pt=0, swap_pt=0):
    buy = (rule['dir'] == 1)
    if rule['type'] == 'GRID':
        sl, tp = rule['sl'], rule['tp']
        sl_col = LINE_COLS[LINE_NAMES.index(sl)] if sl in LINE_NAMES else None
        def fn(ent):
            if sl_col is None:
                return None
            ep = ent['price']
            sv = float(rows[ent['idx']][sl_col])
            if not (0 < sv < 1e12):
                return None
            if buy and sv >= ep:
                return None
            if not buy and sv <= ep:
                return None
            out = simulate_trade(rows, ent['idx'], buy, ep, sl_col, tp,
                                 spread_pt, commission_pt, swap_pt)
            return (out[0], out[2]) if out else None
        return fn
    if rule['type'] == 'SPEC':
        ec = rule['exit_col']
        def fn(ent):
            out = simulate_exit_on_cross(rows, ent['idx'], buy, ec,
                                         commission_pt, swap_pt)
            return (out[0] - spread_pt, out[2]) if out else None
        return fn
    # OPP
    def fn(ent):
        return exit_opposite_cross(rows, ent['idx'], buy,
                                   spread_pt, commission_pt, swap_pt)
    return fn

def rule_label(rule):
    d = 'BUY' if rule['dir'] == 1 else 'SELL'
    if rule['type'] == 'GRID':
        return f"{rule['line']} {d} SL={rule['sl']} TP={rule['tp']}pip"
    if rule['type'] == 'SPEC':
        return f"{rule['line']} {d} exitX={rule['exit_col']}"
    return f"{rule['line']} {d} exit=OPP"

# ============================================================
# SIMULAZIONE A PORTAFOGLIO: 1 posizione per volta, NO trade sovrapposti.
# Le entrate sono processate in ordine cronologico; un segnale che cade mentre
# una posizione e' ancora aperta viene IGNORATO (capitale gia' impegnato).
# Cosi' Sharpe/profit non sono piu' gonfiati da eventi correlati e si puo'
# misurare un vero max drawdown su capitale unico.
# Ritorna (lista trade, curva equity cumulata in punti).
# ============================================================
def simulate_portfolio(pattern_entries, exit_fn):
    trades = []
    equity = [0.0]
    last_exit_idx = -1
    for ent in sorted(pattern_entries, key=lambda e: e['idx']):
        if ent['idx'] <= last_exit_idx:
            continue  # posizione gia' aperta: salta il segnale
        out = exit_fn(ent)
        if out is None:
            continue
        pnl, exit_idx = out
        trades.append({'pnl': pnl, 'entry_idx': ent['idx'],
                       'exit_idx': exit_idx, 'bars': exit_idx - ent['idx']})
        equity.append(equity[-1] + pnl)
        last_exit_idx = exit_idx
    return trades, equity

def portfolio_metrics(trades, equity, total_bars):
    n = len(trades)
    if n == 0:
        return None
    pnls = [t['pnl'] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    # max drawdown picco->minimo sulla curva equity (in punti)
    peak = equity[0]
    maxdd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > maxdd:
            maxdd = dd
    total = equity[-1]
    bars_in_mkt = sum(t['bars'] for t in trades)
    return {
        'n': n,
        'total': total,
        'win_rate': wins / n * 100,
        'avg_pnl': mean(pnls),
        'sharpe': compute_sharpe(pnls),
        'profit_factor': sum(p for p in pnls if p > 0) / max(1, abs(sum(p for p in pnls if p < 0))),
        'max_dd': maxdd,
        'ret_dd': (total / maxdd) if maxdd > 0 else float('inf'),
        'exposure': (bars_in_mkt / total_bars * 100) if total_bars else 0,
        'avg_bars': bars_in_mkt / n,
    }

def penalized_sharpe(sharpe, n):
    # Shrink dello Sharpe verso 0 quando i trade sono pochi (stima rumorosa):
    # n=10 -> x0.5, n=50 -> x0.83, n=200 -> x0.95. Riduce il selection bias.
    return sharpe * n / (n + 10.0)

# ============================================================
# Candidati di pattern come REGOLE (input), dai 3 set di risultati.
# ============================================================
def build_candidates(res1, res2, res3, min_trades, top_each=8):
    cands = []
    for bp in aggregate(res3, ['line', 'dir', 'sl_line', 'tp_pt'], min_trades)[:top_each]:
        line, d, sl, tp = bp['key']
        cands.append({'type': 'GRID', 'line': line, 'dir': d, 'sl': sl, 'tp': tp})
    for bp in aggregate(res2, ['line', 'dir', 'exit_line'], min_trades)[:top_each]:
        line, d, exc = bp['key']
        cands.append({'type': 'SPEC', 'line': line, 'dir': d, 'exit_col': exc})
    for bp in aggregate(res1, ['line', 'dir'], min_trades)[:top_each]:
        line, d = bp['key']
        cands.append({'type': 'OPP', 'line': line, 'dir': d})
    return cands

def run_portfolios(cands, entries, rows, spread_pt, commission_pt, swap_pt):
    out = []
    for rule in cands:
        fn = make_exit_fn(rows, rule, spread_pt, commission_pt, swap_pt)
        pe = [e for e in entries if e['line'] == rule['line'] and e['dir'] == rule['dir']]
        trades, equity = simulate_portfolio(pe, fn)
        m = portfolio_metrics(trades, equity, len(rows))
        if m:
            out.append((rule, m))
    out.sort(key=lambda x: -penalized_sharpe(x[1]['sharpe'], x[1]['n']))
    return out

def print_portfolio_table(port_rows, title, top=15):
    print_section(title)
    print(f"  {'Pattern':<34} {'N':>4} {'TotPt':>9} {'MaxDD':>8} "
          f"{'Ret/DD':>7} {'Expo%':>6} {'Win%':>6} {'Sharpe':>7} {'PF':>6}")
    print('-' * 110)
    for rule, m in port_rows[:top]:
        rd = f"{m['ret_dd']:>7.2f}" if m['ret_dd'] != float('inf') else "    inf"
        print(f"  {rule_label(rule):<34} {m['n']:>4} {m['total']:>+9.0f} "
              f"{m['max_dd']:>8.0f} {rd} {m['exposure']:>5.1f}% "
              f"{m['win_rate']:>5.1f}% {m['sharpe']:>7.2f} {m['profit_factor']:>6.2f}")

# ============================================================
# MOTORE ROBUSTO MULTI-FOLD (walk-forward)
# Array numerici pre-parsati + simulazione GRID veloce (SL dinamico + TP).
# Valuta ogni regola (entry, dir, SL, TP) su N finestre cronologiche separate:
# un pattern e' ROBUSTO solo se profittevole nella maggioranza delle finestre.
# ============================================================
def numeric_arrays(rows):
    n = len(rows)
    H = [0.0]*n; L = [0.0]*n; C = [0.0]*n
    for i, r in enumerate(rows):
        H[i] = float(r['high']); L[i] = float(r['low']); C[i] = float(r['close'])
    sl = {}
    for name in SL_CANDIDATES:
        col = LINE_COLS[LINE_NAMES.index(name)]
        a = [0.0]*n
        for i, r in enumerate(rows):
            try:
                a[i] = float(r[col])
            except (ValueError, KeyError):
                a[i] = 0.0
        sl[name] = a
    cross = {}
    for col in CROSS_COLS:
        ca = [0]*n
        for i, r in enumerate(rows):
            try:
                ca[i] = int(r[col])
            except (ValueError, KeyError):
                ca[i] = 0
        cross[col] = ca
    return H, L, C, sl, cross

def fast_sim_cross(idx, buy, ep, cross_arrs, exit_cols, C, spread, comm, swap, fold_end):
    # Esce al PRIMO crossover OPPOSTO su una delle exit_cols (linea specifica o
    # qualsiasi). Il timeout a fold_end/MAX_BARS resta solo come fallback: di
    # norma il crossover scatta molto prima -> niente dipendenza dal timeout lungo.
    end = min(idx + MAX_BARS, fold_end)
    want = -1 if buy else 1
    for j in range(idx+1, end):
        for col in exit_cols:
            if cross_arrs[col][j] == want:
                bars = j - idx; cost = spread + comm + swap*bars
                pnl = ((C[j] - ep) if buy else (ep - C[j]))/PT_SIZE - cost
                return pnl, j
    j = end - 1
    if j > idx:
        bars = j - idx; cost = spread + comm + swap*bars
        pnl = ((C[j] - ep) if buy else (ep - C[j]))/PT_SIZE - cost
        return pnl, j
    return None

def fast_sim(idx, buy, ep, sl, tp, H, L, C, spread, comm, swap, fold_end):
    # SL dinamico sulla linea (valore noto a barra j-1: niente look-ahead) + TP
    # fisso. Le barre sono limitate a fold_end: i trade NON sconfinano nella
    # finestra successiva (folds indipendenti). Timeout -> mark-to-market.
    end = min(idx + MAX_BARS, fold_end)
    up = ep + tp*PIP_SIZE; dn = ep - tp*PIP_SIZE   # tp in PIP -> livello prezzo
    for j in range(idx+1, end):
        sv = sl[j-1]; bars = j - idx; cost = spread + comm + swap*bars
        if buy:
            if sv > 0 and L[j] <= sv:
                return (sv - ep)/PT_SIZE - cost, j
            if H[j] >= up:
                return tp*10 - cost, j   # PnL in punti = tp(pip)*10
        else:
            if sv > 0 and H[j] >= sv:
                return (ep - sv)/PT_SIZE - cost, j
            if L[j] <= dn:
                return tp*10 - cost, j   # PnL in punti = tp(pip)*10
    j = end - 1
    if j > idx:
        bars = j - idx; cost = spread + comm + swap*bars
        pnl = ((C[j] - ep) if buy else (ep - C[j]))/PT_SIZE - cost
        return pnl, j
    return None

def robust_multifold(all_rows, n_folds, spread_pt, commission_pt, swap_pt, min_trades):
    entries = detect_entries(all_rows, include_line_cross=True)
    H, L, C, sl_arrs, cross_arrs = numeric_arrays(all_rows)
    n = len(all_rows)
    bnds = [round(k*n/n_folds) for k in range(n_folds+1)]
    def fold_of(idx):
        for f in range(n_folds):
            if bnds[f] <= idx < bnds[f+1]:
                return f
        return n_folds-1

    by_ld = defaultdict(list)
    for e in entries:
        by_ld[(e['line'], e['dir'])].append(e)

    # Famiglie di uscita: GRID (SL dinamico + TP) e CROSS (uscita su crossover).
    exit_specs = []
    for sl_name in SL_CANDIDATES:
        for tp in TP_CANDIDATES:
            exit_specs.append(('GRID', sl_name, tp))
    for col in CROSS_COLS:
        exit_specs.append(('CROSS', col, None))   # uscita su crossover linea specifica
    exit_specs.append(('OPP', None, None))         # uscita su primo crossover opposto qualsiasi

    rules = []
    for (line, dir_), ents in by_ld.items():
        ents = sorted(ents, key=lambda x: x['idx'])
        buy = (dir_ == 1)
        for kind, a1, a2 in exit_specs:
            fold_tot = [0.0]*n_folds; fold_n = [0]*n_folds; fold_wins = [0]*n_folds
            fold_last = [-1]*n_folds
            gpnl = []; gbars = 0
            for e in ents:
                idx = e['idx']; f = fold_of(idx)
                if idx <= fold_last[f]:
                    continue  # posizione gia' aperta in questa finestra
                ep = e['price']
                if kind == 'GRID':
                    sl_arr = sl_arrs[a1]; sv0 = sl_arr[idx]
                    if not (0 < sv0 < 1e12):
                        continue
                    if buy and sv0 >= ep:
                        continue
                    if not buy and sv0 <= ep:
                        continue
                    out = fast_sim(idx, buy, ep, sl_arr, a2, H, L, C,
                                   spread_pt, commission_pt, swap_pt, bnds[f+1])
                else:
                    exit_cols = [a1] if kind == 'CROSS' else CROSS_COLS
                    out = fast_sim_cross(idx, buy, ep, cross_arrs, exit_cols, C,
                                         spread_pt, commission_pt, swap_pt, bnds[f+1])
                if out is None:
                    continue
                pnl, ex = out
                fold_last[f] = ex
                fold_tot[f] += pnl; fold_n[f] += 1
                if pnl > 0:
                    fold_wins[f] += 1
                gbars += ex - idx; gpnl.append(pnl)
            total_n = len(gpnl)
            if total_n < min_trades:
                continue
            active = sum(1 for x in fold_n if x > 0)
            if active < max(3, n_folds-1):
                continue  # il segnale deve comparire in piu' regimi, non in uno solo
            pos = sum(1 for i in range(n_folds) if fold_n[i] > 0 and fold_tot[i] > 0)
            eq = 0.0; peak = 0.0; mdd = 0.0
            for p in gpnl:
                eq += p; peak = max(peak, eq); mdd = max(mdd, peak - eq)
            rules.append({
                'line': line, 'dir': dir_, 'exit': kind,
                'sl': a1 if kind == 'GRID' else None,
                'tp': a2 if kind == 'GRID' else None,
                'exit_col': a1 if kind == 'CROSS' else None,
                'n': total_n, 'active': active, 'pos': pos,
                'total': eq, 'mdd': mdd,
                'retdd': (eq/mdd) if mdd > 0 else float('inf'),
                'win': sum(fold_wins)/total_n*100,
                'sharpe': compute_sharpe(gpnl),
                'fold_tot': fold_tot, 'fold_n': fold_n,
                'avg_bars': gbars/total_n, 'exposure': gbars/n*100,
            })
    rules.sort(key=lambda r: (-(r['pos']/r['active']),
                              -penalized_sharpe(r['sharpe'], r['n']), -r['total']))
    return rules, n_folds

def rule_label_robust(r):
    d = 'BUY' if r['dir'] == 1 else 'SELL'
    if r['exit'] == 'GRID':
        return f"{r['line']} {d} SL={r['sl']} TP={r['tp']}pip"
    if r['exit'] == 'CROSS':
        return f"{r['line']} {d} exitX={r['exit_col']}"
    return f"{r['line']} {d} exit=OPP"

def print_robust(rules, n_folds, min_trades, top=40):
    print_section(f"ANALISI ROBUSTA MULTI-FOLD ({n_folds} finestre walk-forward) "
                  f"— entry prezzo-linea + linea-linea")
    print("  ROBUSTO = profittevole in TUTTE le finestre attive (Ret/DD>=1).")
    print("  'Folds' = segno PnL per finestra cronologica ( + positiva / - negativa / . assente ).")
    print("  Entry 'X...' = crossover linea-linea. Exit: SL/TP, exitX=cross linea, OPP=primo")
    print("  cross opposto. AvgBars basso = uscita rapida (non dipende dal timeout lungo).\n")
    print(f"  {'Pattern':<30} {'Folds':<7} {'Pos':>4} {'N':>5} {'TotPt':>9} "
          f"{'MaxDD':>8} {'Ret/DD':>7} {'Win%':>6} {'Bars':>5} {'Sharpe':>7}")
    print('-'*112)
    robusti = []
    for r in rules[:top]:
        fp = ''.join('+' if (r['fold_n'][i] > 0 and r['fold_tot'][i] > 0)
                     else ('.' if r['fold_n'][i] == 0 else '-') for i in range(n_folds))
        rd = f"{r['retdd']:>7.2f}" if r['retdd'] != float('inf') else "    inf"
        lbl = rule_label_robust(r)
        is_rob = (r['pos'] == r['active'] and r['active'] >= n_folds-1
                  and r['retdd'] >= 1 and r['n'] >= min_trades)
        if is_rob:
            robusti.append(r)
        mark = '  <== ROBUSTO' if is_rob else ''
        print(f"  {lbl:<30} {fp:<7} {r['pos']:>2}/{r['active']:<2} {r['n']:>5} "
              f"{r['total']:>+9.0f} {r['mdd']:>8.0f} {rd} {r['win']:>5.1f}% "
              f"{r['avg_bars']:>5.0f} {r['sharpe']:>7.2f}{mark}")
    print(f"\n  Pattern ROBUSTI (positivi in tutte le finestre attive + Ret/DD>=1): {len(robusti)}")
    if robusti:
        print("  Ordinati per affidabilita'. Questi sono i candidati da testare su altri simboli:")
        for r in robusti[:12]:
            print(f"    {rule_label_robust(r):<32} | {r['n']:>4} trade | "
                  f"TotPt {r['total']:>+7.0f} | Ret/DD {r['retdd']:>5.2f} | "
                  f"Win {r['win']:>3.0f}% | {r['avg_bars']:>3.0f} barre")
    else:
        print("  NESSUN pattern e' positivo su tutte le finestre: nessun edge robusto su questo")
        print("  simbolo con queste regole. Meglio saperlo ora che con denaro reale.")

# ============================================================
# MAIN
# ============================================================
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    path = sys.argv[1]

    # Default parametri
    spread_pt = 15
    commission_pt = 0    # commissione round-trip in punti (es. 7 = 0.7 pip)
    swap_pt = 0.0        # swap in punti per barra D1 tenuta (puo' essere negativo)
    train_pct = 1.0
    split_date = None
    min_trades = 10
    debug_n = 0
    out_path = None
    ctx_filters = {}
    robust_mode = False
    n_folds = 5

    for arg in sys.argv[2:]:
        if arg == '--robust':
            robust_mode = True
        elif arg.startswith('--folds='):
            n_folds = int(arg.split('=', 1)[1])
        elif arg.startswith('--output='):
            out_path = arg.split('=', 1)[1]
        elif arg.startswith('--spread='):
            spread_pt = int(arg.split('=', 1)[1])
        elif arg.startswith('--commission='):
            commission_pt = float(arg.split('=', 1)[1])
        elif arg.startswith('--swap='):
            swap_pt = float(arg.split('=', 1)[1])
        elif arg.startswith('--train-pct='):
            train_pct = float(arg.split('=', 1)[1])
        elif arg.startswith('--split-date='):
            split_date = arg.split('=', 1)[1]
        elif arg.startswith('--min-trades='):
            min_trades = int(arg.split('=', 1)[1])
        elif arg.startswith('--debug='):
            debug_n = int(arg.split('=', 1)[1])
        elif '=' in arg:
            k, v = arg.split('=', 1)
            ctx_filters[k] = float(v) if ('.' in v or 'e' in v.lower()) else int(v)

    if not os.path.exists(path):
        print(f"File non trovato: {path}")
        return

    if out_path:
        logfile = open(out_path, 'w', encoding='utf-8')
        sys.stdout = Tee(sys.__stdout__, logfile)

    print(f"Caricamento {path}...")
    all_rows = load_csv(path)
    print(f"  Righe totali: {len(all_rows)}")
    if len(all_rows) < 50:
        print("Troppo pochi dati.")
        return
    print(f"  Date: {all_rows[-1]['datetime']} -> {all_rows[0]['datetime']}")

    # Verifica colonne
    if not all(cc in all_rows[0] for cc in CROSS_COLS):
        print("ERRORE: colonne crossover mancanti. Rigenera il CSV con Export_PAPP v2.01.")
        print(f"  Cerco: {CROSS_COLS}")
        return

    # ============================================================
    # MODALITA' ROBUSTA MULTI-FOLD (--robust): re-analisi completa
    # entry prezzo-linea + linea-linea, validazione walk-forward.
    # ============================================================
    if robust_mode:
        if not all(pc in all_rows[0] for pc in PAIR_COLS):
            print(f"ERRORE: colonne linea-linea mancanti {PAIR_COLS}. Rigenera il CSV.")
            return
        # all_rows e' gia' oldest-first (cronologico): ok per walk-forward.
        print(f"\nMODALITA' ROBUSTA: {n_folds} finestre walk-forward | "
              f"costi spread={spread_pt} comm={commission_pt} swap={swap_pt} | min-trades={min_trades}")
        rules, nf = robust_multifold(all_rows, n_folds, spread_pt, commission_pt,
                                     swap_pt, min_trades)
        print_robust(rules, nf, min_trades)
        print(f"\nFatto.\n")
        return

    # Split train/test
    train_rows, test_rows = split_train_test(all_rows, train_pct, split_date)
    print(f"\n  Training set: {len(train_rows)} barre")
    if test_rows:
        print(f"  Test set:     {len(test_rows)} barre")
    else:
        print(f"  Test set:     nessuno (100% training)")

    # Work on training set
    rows = train_rows

    print(f"\nRilevamento entrate (crossover D1 reali)...")
    all_entries = detect_entries(rows)
    print(f"  Segnali totali: {len(all_entries)}")
    by_line = defaultdict(int)
    for e in all_entries:
        by_line[e['line']] += 1
    for ln in LINE_NAMES:
        print(f"    {ln:<10}: {by_line[ln]:>5}")
    print(f"  BUY: {sum(1 for e in all_entries if e['dir']==1)}, "
          f"SELL: {sum(1 for e in all_entries if e['dir']==-1)}")

    # Applica filtri
    if ctx_filters:
        print(f"\n  Filtri contestuali:")
        for k, v in ctx_filters.items():
            print(f"    {k} = {v}")
        entries = apply_context_filters(all_entries, ctx_filters)
        print(f"  Entrate dopo filtri: {len(entries)}")
    else:
        entries = all_entries

    if len(entries) < min_trades:
        print("Troppo poche entrate. Abbassa i filtri o usa --min-trades.")
        return

    print(f"\nCosti applicati: spread={spread_pt}pt ({spread_pt/10:.1f} pip), "
          f"commissione={commission_pt}pt, swap={swap_pt}pt/barra")
    if commission_pt == 0 and swap_pt == 0:
        print("  ATTENZIONE: commissione e swap a 0. Usa --commission= e --swap= "
              "per costi realistici (lo swap pesa sui pattern a lunga tenuta).")
    print("  NOTA: Sharpe = PER-TRADE (avg/sd), non annualizzato. Per annualizzare "
          "moltiplica per sqrt(trade/anno).")

    # ============================================================
    # LEGENDA / METODOLOGIA — rende il report leggibile da solo
    # ============================================================
    print_section("LEGENDA E METODOLOGIA")
    print("  Entrata: sempre un CROSSOVER su D1 reali (il prezzo taglia una linea MA/Mediana).")
    print("  Le analisi differiscono solo nel modo di USCIRE dal trade:")
    print("    ANALISI 1  exit = primo crossover OPPOSTO su una linea QUALSIASI")
    print("    ANALISI 2  exit = crossover di una linea SPECIFICA (opposta)")
    print("    ANALISI 3  exit = SL dinamico su una linea + TP fisso (griglia SL x TP)")
    print("  Costi: spread + commissione sottratti a ogni trade; swap per barra tenuta.")
    print("  Unita': TP in PIP (come gli input EA); PnL/metriche in PUNTI (1 pip = 10 punti).")
    print("")
    print("  COLONNE:")
    print("    Trades   numero di operazioni del pattern")
    print("    Win%     percentuale di trade chiusi in profitto")
    print("    AvgPts   profitto medio per trade (punti)")
    print("    Sharpe   profitto medio / deviazione standard, PER-TRADE (CV<10% -> azzerato)")
    print("    ProfitF  profitti lordi / perdite lorde   (>1 = sistema in attivo)")
    print("    TotPnl   profitto totale del pattern (punti)")
    print("    AvgBars  durata media del trade (barre D1)")
    print("    MaxDD    massima perdita picco->minimo sull'equity (portafoglio 1 pos/volta)")
    print("    Ret/DD   TotPnl / MaxDD   (piu' alto = meglio per unita' di rischio)")
    print("    Expo%    frazione di tempo a mercato")
    print("")
    print("  VALIDAZIONE: i pattern trovati sul TRAINING (<= split) sono ri-testati sul")
    print("    TEST (> split). Train_Sh/Test_Sh = Sharpe nei due periodi.")
    print("  SELEZIONE ROBUSTA: tiene SOLO i pattern positivi su TRAIN *e* TEST (difesa")
    print("    dall'overfitting). Punteggio = min(Sharpe penalizzato train, test).")
    print("  --robust: variante walk-forward a N finestre; ROBUSTO = positivo in TUTTE.")

    if not test_rows:
        print("\n  " + "!"*72)
        print("  !! IN-SAMPLE AL 100%: nessun test set. I 'migliori' pattern sono")
        print("  !! soggetti a selection bias (centinaia di combinazioni testate).")
        print("  !! Usa --split-date=YYYY.MM.DD o --train-pct=0.7 per validare OOS.")
        print("  " + "!"*72)

    # ============================================================
    # DEBUG: stampa i primi N trade per verifica manuale
    # ============================================================
    if debug_n > 0:
        print(f"\n{'='*140}")
        print(f"  DEBUG: primi {debug_n} trade Analisi 3 (verifica manuale)")
        print(f"{'='*140}")
        count = 0
        for ent in entries[:debug_n]:
            if count >= debug_n:
                break
            buy = (ent['dir'] == 1)
            for sl_name in ['MA365', 'MA30']:
                sl_col = LINE_COLS[LINE_NAMES.index(sl_name)]
                sl_val = float(rows[ent['idx']][sl_col])
                if not (sl_val > 0 and sl_val < 1e12):
                    continue
                if buy and sl_val >= ent['price']:
                    continue
                if not buy and sl_val <= ent['price']:
                    continue
                for tp_pt in [60, 120]:
                    out = simulate_trade(rows, ent['idx'], buy, ent['price'],
                                         sl_col, tp_pt, spread_pt)
                    if out is None:
                        continue
                    pnl, etype, eidx, eline = out
                    exit_row = rows[eidx]
                    exit_close = float(exit_row['close'])
                    print(f"  [{count+1}] {ent['datetime']} | {ent['line']} "
                          f"{'BUY' if buy else 'SELL'} "
                          f"@ {ent['price']:.5f} | "
                          f"SL={sl_name}({sl_val:.5f}) TP={tp_pt}pip | "
                          f"-> {etype} @ {exit_row['datetime']} "
                          f"({exit_close:.5f}) | "
                          f"PnL={pnl:+.0f}pt | {eidx-ent['idx']} barre")
                    count += 1
                    if count >= debug_n:
                        break
                if count >= debug_n:
                    break
        print()

    # ============================================================
    # ANALISI 1
    # ============================================================
    print_section("ANALISI 1: Entry = crossover D1, Exit = prossimo crossover opposto (qualsiasi)")
    res1 = analyze_cross_to_opposite(entries, rows, spread_pt, commission_pt, swap_pt)
    print(f"  Trade chiusi: {len(res1)}")
    if res1:
        p1 = aggregate(res1, ['line', 'dir'], min_trades)
        print_table(p1, ['entry_line', 'dir'], "Pattern: (entry_line, dir)", top=15)

    # ============================================================
    # ANALISI 2
    # ============================================================
    print_section("ANALISI 2: Entry = crossover, Exit = crossover su linea specifica (opposta)")
    res2 = analyze_cross_to_specific(entries, rows, spread_pt, commission_pt, swap_pt)
    print(f"  Trade chiusi: {len(res2)}")
    if res2:
        p2 = aggregate(res2, ['line', 'dir', 'exit_line'], min_trades)
        print_table(p2, ['entry_line', 'dir', 'exit_line'],
                    "Pattern: (entry_line, dir, exit_line)", top=25)

    # ============================================================
    # ANALISI 3 - Grid Search con SL DINAMICO
    # ============================================================
    print_section("ANALISI 3: Entry = crossover, Exit = SL dinamico su linea + TP fisso")
    res3 = analyze_dynamic_sl_grid(entries, rows, spread_pt, commission_pt, swap_pt)
    print(f"  Trade chiusi: {len(res3)}")
    if res3:
        p3 = aggregate(res3, ['line', 'dir', 'sl_line', 'tp_pt'], min_trades)
        print_table(p3, ['entry_line', 'dir', 'sl_line', 'tp_pt'],
                    "Pattern: (entry_line, dir, sl_line, tp_pt)", top=30)

        # Miglior SL aggregato
        print(f"\n  MIGLIOR SL LINEA (media PnL su tutti i pattern)")
        print(f"  " + "-"*60)
        sl_perf = defaultdict(list)
        for r in res3:
            sl_perf[r['sl_line']].append(r['pnl_pt'])
        for sl, pnls in sorted(sl_perf.items(),
                               key=lambda x: -sum(1 for p in x[1] if p>0)/len(x[1])):
            wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100
            print(f"    SL={sl:<8} -> PnL medio {mean(pnls):>+7.1f}  "
                  f"Win% {wr:>5.1f}%  Sharpe {compute_sharpe(pnls):.2f}  "
                  f"(su {len(pnls)} trade)")

        # Miglior TP aggregato
        print(f"\n  MIGLIOR TP (media PnL per TP)")
        print(f"  " + "-"*60)
        tp_perf = defaultdict(list)
        for r in res3:
            tp_perf[r['tp_pt']].append(r['pnl_pt'])
        for tp, pnls in sorted(tp_perf.items(), key=lambda x: -mean(x[1])):
            wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100
            print(f"    TP={tp:<4}pip -> PnL medio {mean(pnls):>+7.1f}  "
                  f"Win% {wr:>5.1f}%  Sharpe {compute_sharpe(pnls):.2f}  "
                  f"(su {len(pnls)} trade)")

    # ============================================================
    # RIEPILOGO su TRAINING
    # ============================================================
    all_train = res1 + res2 + res3
    print_summary(all_train, min_trades)

    # ============================================================
    # ANALISI PORTAFOGLIO (TRAINING): equity sequenziale, 1 posizione/volta
    # Risolve il problema dei trade sovrapposti: i segnali che cadono mentre
    # una posizione e' aperta vengono ignorati (capitale unico). Misura il
    # vero max drawdown e l'exposure, impossibili nelle statistiche per-trade.
    # ============================================================
    cands = build_candidates(res1, res2, res3, min_trades, top_each=8)
    train_port = run_portfolios(cands, entries, rows, spread_pt, commission_pt, swap_pt)
    if train_port:
        print_portfolio_table(train_port,
            "ANALISI PORTAFOGLIO (TRAINING): 1 posizione/volta, equity sequenziale", top=15)
        print("\n  NOTA: trade sovrapposti ESCLUSI (capitale unico). MaxDD = max perdita")
        print("        picco->minimo in punti; Ret/DD = TotPt/MaxDD (piu' alto = meglio);")
        print("        Expo% = frazione di tempo a mercato. Ordinati per Sharpe penalizzato.")

    # ============================================================
    # TEST SET (se disponibile)
    # ============================================================
    if test_rows:
        print_section("VALIDAZIONE TEST SET")
        test_entries = detect_entries(test_rows)
        if ctx_filters:
            test_entries = apply_context_filters(test_entries, ctx_filters)
        print(f"  Entrate nel test set: {len(test_entries)}")

        if test_entries:
            # Riepiloga i migliori pattern del training e valuta sul test
            best_patterns = aggregate(all_train,
                                      ['line', 'dir', 'exit_line', 'exit_type',
                                       'tp_pt', 'sl_line'],
                                      min_trades)[:20]

            print(f"\n  Top 20 pattern del training validati sul test:")
            print(f"  {'Pattern':<60} {'Train_Sh':>8} {'Test_Sh':>8} "
                  f"{'Train_N':>8} {'Test_N':>8} {'Train_Win':>8} {'Test_Win':>8}")
            print('-'*120)

            for bp in best_patterns:
                k = bp['key']
                line, d, ex_line, etype, tp, sl = k

                # Valuta sul test
                test_trades = []
                for te in test_entries:
                    if te['line'] != line or te['dir'] != d:
                        continue
                    buy = (d == 1)
                    if etype in ('SL', 'TP'):
                        sl_col = LINE_COLS[LINE_NAMES.index(sl)] if sl and sl in LINE_NAMES else None
                        if sl_col:
                            out = simulate_trade(test_rows, te['idx'], buy, te['price'],
                                                 sl_col, tp, spread_pt, commission_pt, swap_pt)
                            if out:
                                test_trades.append(out[0])
                    elif etype in ('OPP_CROSS', 'SPEC_CROSS'):
                        ec_col = ex_line if ex_line in CROSS_COLS else None
                        if ec_col:
                            out = simulate_exit_on_cross(test_rows, te['idx'], buy, ec_col,
                                                         commission_pt, swap_pt)
                            if out:
                                test_trades.append(out[0] - spread_pt)

                if len(test_trades) >= min_trades:
                    test_sh = compute_sharpe(test_trades)
                else:
                    test_sh = 0

                label = f"{line} {'BUY' if d==1 else 'SELL'} | {ex_line} | {etype}"
                if tp:
                    label += f" TP={tp}pip"
                if sl:
                    label += f" SL={sl}"
                print(f"  {label:<60} {bp['sharpe']:>8.2f} {test_sh:>8.2f} "
                      f"{bp['trades']:>8} {len(test_trades):>8} "
                      f"{bp['win_rate']:>7.1f}% "
                      f"{sum(1 for p in test_trades if p>0)/max(1,len(test_trades))*100:>7.1f}%")

            # ====================================================
            # SELEZIONE ROBUSTA: portafoglio su TRAIN *e* TEST.
            # Un pattern e' "robusto" solo se resta profittevole su entrambi i
            # set (no overfitting). Punteggio = min(Sharpe penalizzato train,
            # Sharpe penalizzato test): premia chi e' buono su ENTRAMBI, non chi
            # spicca solo in-sample. Difende dal selection bias delle centinaia
            # di combinazioni testate.
            # ====================================================
            min_test_n = max(5, min_trades // 2)
            robust = []
            for rule, mtr in train_port:
                fn_te = make_exit_fn(test_rows, rule, spread_pt, commission_pt, swap_pt)
                pe_te = [e for e in test_entries
                         if e['line'] == rule['line'] and e['dir'] == rule['dir']]
                tr_te, eq_te = simulate_portfolio(pe_te, fn_te)
                mte = portfolio_metrics(tr_te, eq_te, len(test_rows))
                if mte is None or mte['n'] < min_test_n:
                    continue
                consistent = (mtr['total'] > 0 and mte['total'] > 0)
                rob = (min(penalized_sharpe(mtr['sharpe'], mtr['n']),
                           penalized_sharpe(mte['sharpe'], mte['n']))
                       if consistent else -999.0)
                robust.append((rule, mtr, mte, rob))
            robust.sort(key=lambda x: -x[3])

            print_section("SELEZIONE ROBUSTA: pattern consistenti TRAIN + TEST (portafoglio)")
            if not robust:
                print("  [nessun pattern con abbastanza trade nel test set]")
            else:
                print(f"  {'Pattern':<34} {'TrTot':>8} {'TeTot':>8} {'TrDD':>7} "
                      f"{'TeDD':>7} {'TrSh':>6} {'TeSh':>6} {'RobScore':>9}")
                print('-' * 110)
                for rule, mtr, mte, rob in robust:
                    rob_s = f"{rob:>9.2f}" if rob > -900 else f"{'  perde':>9}"
                    print(f"  {rule_label(rule):<34} {mtr['total']:>+8.0f} {mte['total']:>+8.0f} "
                          f"{mtr['max_dd']:>7.0f} {mte['max_dd']:>7.0f} "
                          f"{mtr['sharpe']:>6.2f} {mte['sharpe']:>6.2f} {rob_s}")
                best = robust[0]
                if best[3] > 0:
                    print(f"\n  >>> Pattern PIU' ROBUSTO: {rule_label(best[0])}")
                    print(f"      Train: {best[1]['total']:+.0f}pt / DD {best[1]['max_dd']:.0f} "
                          f"(Ret/DD {best[1]['ret_dd']:.2f})  |  "
                          f"Test: {best[2]['total']:+.0f}pt / DD {best[2]['max_dd']:.0f}")
                else:
                    print("\n  >>> ATTENZIONE: nessun pattern resta profittevole su ENTRAMBI i set.")
                    print("      Probabile overfitting: i 'migliori' del training non reggono OOS.")

    print(f"\nFatto.\n")

if __name__ == '__main__':
    main()
