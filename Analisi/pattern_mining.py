#!/usr/bin/env python3
"""
Pattern Mining per PaPP Median v3 - CORRETTO
- Crossover calcolati su D1 reali (non interpolati)
- SL dinamico: prezzo tocca la linea (segue il movimento)
- Spread/commissioni configurabili
- Walk-forward: training set + test set separati
- Sharpe ratio: std=0 gestito correttamente
- Filtri contestuali attivi

Uso: python3 pattern_mining.py <PAPP_Export.csv> [opzioni]

Opzioni:
  --spread=N          Spread in punti (default: 15 = 1.5 pip EURUSD)
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

PT_SIZE  = 0.00001
MAX_BARS = 200

LINE_NAMES = ['MA365', 'MA182', 'MA121', 'MA30', 'MA14', 'MA7', 'MA3', 'Median']
LINE_COLS  = ['MA365', 'MA182', 'MA121', 'MA30', 'MA14', 'MA7', 'MA3', 'median']
CROSS_COLS = ['crossMA365', 'crossMA182', 'crossMA121', 'crossMA30',
              'crossMA14', 'crossMA7', 'crossMA3', 'crossMed']
ABOVE_COLS = ['a365', 'a182', 'a121', 'a30', 'a14', 'a7', 'a3', 'aMed']

SL_CANDIDATES = ['MA14', 'MA30', 'MA121', 'MA365', 'Median']
TP_CANDIDATES = [20, 30, 40, 50, 60, 80, 100, 120, 150]

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

def detect_entries(rows):
    entries = []
    prev_d1_idx = {}
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
    return entries

# ============================================================
# SHARPE CORRETTO: gestisce std=0
# ============================================================
def compute_sharpe(pnls):
    if len(pnls) < 2:
        return 0.0
    avg = mean(pnls)
    try:
        sd = stdev(pnls)
    except:
        sd = 0
    if sd == 0:
        return 99.0 if avg > 0 else (-99.0 if avg < 0 else 0.0)
    return avg / sd * sqrt(252)

# ============================================================
# SIMULAZIONE TRADE: SL DINAMICO sulla linea, TP fisso
# ============================================================
def simulate_trade(rows, entry_idx, buy, entry_price, sl_col, tp_pt,
                   spread_pt=0, max_bars=MAX_BARS):
    for j in range(entry_idx+1, min(entry_idx+max_bars, len(rows))):
        row = rows[j]
        hi = float(row['high'])
        lo = float(row['low'])
        sl_val = float(row[sl_col])

        # SL DINAMICO: il prezzo tocca la linea
        if buy and lo <= sl_val:
            exit_price = sl_val
            pnl = (exit_price - entry_price) / PT_SIZE - spread_pt
            return pnl, 'SL', j, sl_col
        if not buy and hi >= sl_val:
            exit_price = sl_val
            pnl = (entry_price - exit_price) / PT_SIZE - spread_pt
            return pnl, 'SL', j, sl_col

        # TP fisso
        if buy and hi >= entry_price + tp_pt * PT_SIZE:
            return tp_pt - spread_pt, 'TP', j, 'TP'
        if not buy and lo <= entry_price - tp_pt * PT_SIZE:
            return tp_pt - spread_pt, 'TP', j, 'TP'

    return None

# ============================================================
# USCITA SU CROSSOVER DI LINEA SPECIFICA (in direzione opposta)
# ============================================================
def simulate_exit_on_cross(rows, entry_idx, buy, exit_cross_col, max_bars=MAX_BARS):
    entry_price = float(rows[entry_idx]['close'])
    for j in range(entry_idx+1, min(entry_idx+max_bars, len(rows))):
        row = rows[j]
        close_j = float(row['close'])
        cv = int(row.get(exit_cross_col, 0))
        if cv == 0:
            continue
        if buy and cv == -1:
            return (close_j - entry_price) / PT_SIZE, 'CROSS', j, exit_cross_col
        if not buy and cv == 1:
            return (entry_price - close_j) / PT_SIZE, 'CROSS', j, exit_cross_col
    return None

# ============================================================
# ANALISI 1: Entry su crossover → exit su prossimo crossover opposto (qualsiasi linea)
# ============================================================
def analyze_cross_to_opposite(entries, rows, spread_pt=0):
    results = []
    for ent in entries:
        buy = (ent['dir'] == 1)
        entry_price = ent['price']
        idx = ent['idx']
        for j in range(idx+1, min(idx+MAX_BARS, len(rows))):
            row = rows[j]
            close_j = float(row['close'])
            hit = False
            for cross_col in CROSS_COLS:
                cv = int(row.get(cross_col, 0))
                if cv == 0:
                    continue
                if buy and cv == -1:
                    pnl = (close_j - entry_price) / PT_SIZE - spread_pt
                    results.append({**ent, 'exit_line': cross_col, 'exit_type': 'OPP_CROSS',
                                    'bars_held': j-idx, 'pnl_pt': pnl, 'exit_idx': j})
                    hit = True
                    break
                if not buy and cv == 1:
                    pnl = (entry_price - close_j) / PT_SIZE - spread_pt
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
def analyze_cross_to_specific(entries, rows, spread_pt=0):
    results = []
    for ent in entries:
        buy = (ent['dir'] == 1)
        for exit_cross_col in CROSS_COLS:
            ex = simulate_exit_on_cross(rows, ent['idx'], buy, exit_cross_col)
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
def analyze_dynamic_sl_grid(entries, rows, spread_pt=0):
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
                                         sl_col, tp_pt, spread_pt)
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
            extra = f" TP={tp}" if tp else ""
            extra += f" SL={sl}" if sl else ""
            extra += f" [{etype}]" if etype else ""
            print(f"  {line:<10} -> {d_str:<5} | exit={ex:<10}{extra:<25} | "
                  f"Sharpe={sh:>6.2f} | Win={wr:>5.0f}% | Avg={avg:>+7.1f}pt | N={n:>5}")

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
    train_pct = 1.0
    split_date = None
    min_trades = 10
    debug_n = 0
    ctx_filters = {}

    for arg in sys.argv[2:]:
        if arg.startswith('--spread='):
            spread_pt = int(arg.split('=', 1)[1])
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

    print(f"\nSpread applicato: {spread_pt}pt ({spread_pt/10:.1f} pip)")

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
                          f"SL={sl_name}({sl_val:.5f}) TP={tp_pt} | "
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
    res1 = analyze_cross_to_opposite(entries, rows, spread_pt)
    print(f"  Trade chiusi: {len(res1)}")
    if res1:
        p1 = aggregate(res1, ['line', 'dir'], min_trades)
        print_table(p1, ['entry_line', 'dir'], "Pattern: (entry_line, dir)", top=15)

    # ============================================================
    # ANALISI 2
    # ============================================================
    print_section("ANALISI 2: Entry = crossover, Exit = crossover su linea specifica (opposta)")
    res2 = analyze_cross_to_specific(entries, rows, spread_pt)
    print(f"  Trade chiusi: {len(res2)}")
    if res2:
        p2 = aggregate(res2, ['line', 'dir', 'exit_line'], min_trades)
        print_table(p2, ['entry_line', 'dir', 'exit_line'],
                    "Pattern: (entry_line, dir, exit_line)", top=25)

    # ============================================================
    # ANALISI 3 - Grid Search con SL DINAMICO
    # ============================================================
    print_section("ANALISI 3: Entry = crossover, Exit = SL dinamico su linea + TP fisso")
    res3 = analyze_dynamic_sl_grid(entries, rows, spread_pt)
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
            print(f"    TP={tp:<4}pt -> PnL medio {mean(pnls):>+7.1f}  "
                  f"Win% {wr:>5.1f}%  Sharpe {compute_sharpe(pnls):.2f}  "
                  f"(su {len(pnls)} trade)")

    # ============================================================
    # RIEPILOGO su TRAINING
    # ============================================================
    all_train = res1 + res2 + res3
    print_summary(all_train, min_trades)

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
                                                 sl_col, tp, spread_pt)
                            if out:
                                test_trades.append(out[0])
                    elif etype in ('OPP_CROSS', 'SPEC_CROSS'):
                        ec_col = ex_line if ex_line in CROSS_COLS else None
                        if ec_col:
                            out = simulate_exit_on_cross(test_rows, te['idx'], buy, ec_col)
                            if out:
                                test_trades.append(out[0] - spread_pt)

                if len(test_trades) >= min_trades:
                    test_sh = compute_sharpe(test_trades)
                else:
                    test_sh = 0

                label = f"{line} {'BUY' if d==1 else 'SELL'} | {ex_line} | {etype}"
                if tp:
                    label += f" TP={tp}"
                if sl:
                    label += f" SL={sl}"
                print(f"  {label:<60} {bp['sharpe']:>8.2f} {test_sh:>8.2f} "
                      f"{bp['trades']:>8} {len(test_trades):>8} "
                      f"{bp['win_rate']:>7.1f}% "
                      f"{sum(1 for p in test_trades if p>0)/max(1,len(test_trades))*100:>7.1f}%")

    print(f"\nFatto.\n")

if __name__ == '__main__':
    main()
