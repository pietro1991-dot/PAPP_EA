#!/usr/bin/env python3
"""
Pattern Mining per PaPP Median v2
Trova pattern di entrata e uscita per TUTTE le 8 linee (3/7/14/30/121/182/365/Median).
Legge il CSV da Export_PAPP.mq5 con crossover direzionali (+1/-1/0).

Strategia:
  - Entrata: quando una linea viene incrociata dal prezzo (+1 bullish, -1 bearish)
  - Uscita: quando il prezzo incrocia un'altra linea (o la stessa in direzione opposta)
  - Ogni pattern (entry_line, entry_dir, exit_line, exit_dir) viene valutato
  - Supporta anche TP/SL fissi e filtri contestuali (cluster, vol, orderScore, etc.)
"""
import csv, sys, os
from collections import defaultdict
from statistics import mean, stdev, median
from math import sqrt

PT_SIZE  = 0.00001
MAX_BARS = 200

# ============================================================
# NOMI LINEE (in ordine: lento -> veloce)
# ============================================================
LINE_NAMES = ['MA365', 'MA182', 'MA121', 'MA30', 'MA14', 'MA7', 'MA3', 'Median']
LINE_COLS  = ['MA365', 'MA182', 'MA121', 'MA30', 'MA14', 'MA7', 'MA3', 'median']
CROSS_COLS = ['crossMA365', 'crossMA182', 'crossMA121', 'crossMA30',
              'crossMA14', 'crossMA7', 'crossMA3', 'crossMed']
ABOVE_COLS = ['a365', 'a182', 'a121', 'a30', 'a14', 'a7', 'a3', 'aMed']

# ============================================================
# CARICA CSV
# ============================================================
def load_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))

# ============================================================
# CONTESTO DI ENTRATA
# ============================================================
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

# ============================================================
# RILEVA ENTRATE: cerca tutte le barre con crossover
# ============================================================
def detect_entries(rows):
    entries = []
    for i, row in enumerate(rows):
        for line_name, cross_col in zip(LINE_NAMES, CROSS_COLS):
            cross_val = int(row.get(cross_col, 0))
            if cross_val == 0:
                continue
            entries.append({
                'idx': i,
                'line': line_name,
                'dir': cross_val,       # +1 = bullish, -1 = bearish
                'price': float(row['close']),
                'datetime': row['datetime'],
                'ctx': entry_context(row),
            })
    return entries

# ============================================================
# CERCA USCITA: dato un entry, trova la prossima uscita
# ============================================================
def find_exit(rows, entry, max_bars=MAX_BARS):
    i = entry['idx']
    entry_price = entry['price']
    entry_dir = entry['dir']   # +1 = BUY, -1 = SELL
    entry_line = entry['line']

    buy = (entry_dir == 1)

    for j in range(i+1, min(i+max_bars, len(rows))):
        row = rows[j]
        hi, lo = float(row['high']), float(row['low'])
        close_j = float(row['close'])

        # Controlla ogni linea per uscita
        for exit_line, cross_col in zip(LINE_NAMES, CROSS_COLS):
            cross_val = int(row.get(cross_col, 0))
            if cross_val == 0:
                continue

            # Determina se questo crossover e' un'uscita valida per la nostra entry
            exit_dir = cross_val

            # BUY entry: esci su crossover bearish (-1) di QUALSIASI linea
            # SELL entry: esci su crossover bullish (+1) di QUALSIASI linea
            if buy and exit_dir == -1:
                exit_price = close_j
                pnl_pt = (exit_price - entry_price) / PT_SIZE
                return {
                    'exit_line': exit_line,
                    'exit_dir': exit_dir,
                    'exit_idx': j,
                    'bars_held': j - i,
                    'pnl_pt': pnl_pt,
                    'exit_price': exit_price,
                    'exit_type': 'cross',
                }

            if not buy and exit_dir == 1:
                exit_price = close_j
                pnl_pt = (entry_price - exit_price) / PT_SIZE
                return {
                    'exit_line': exit_line,
                    'exit_dir': exit_dir,
                    'exit_idx': j,
                    'bars_held': j - i,
                    'pnl_pt': pnl_pt,
                    'exit_price': exit_price,
                    'exit_type': 'cross',
                }

    return None

# ============================================================
# CERCA USCITA SU LINEA SPECIFICA
# ============================================================
def find_exit_on_line(rows, entry, exit_line_name, max_bars=MAX_BARS):
    """Esce solo quando incrocia una linea specifica (in direzione opposta all'entry)"""
    i = entry['idx']
    entry_price = entry['price']
    entry_dir = entry['dir']
    buy = (entry_dir == 1)

    # Trova colonne per la linea di uscita
    try:
        li = LINE_NAMES.index(exit_line_name)
    except ValueError:
        return None
    exit_cross_col = CROSS_COLS[li]

    for j in range(i+1, min(i+max_bars, len(rows))):
        row = rows[j]
        close_j = float(row['close'])
        cross_val = int(row.get(exit_cross_col, 0))

        if cross_val == 0:
            continue

        # BUY: esci su bearish cross (-1) della exit_line
        # SELL: esci su bullish cross (+1) della exit_line
        if buy and cross_val == -1:
            pnl_pt = (close_j - entry_price) / PT_SIZE
            return {'exit_line': exit_line_name, 'exit_idx': j,
                    'bars_held': j - i, 'pnl_pt': pnl_pt, 'exit_price': close_j,
                    'exit_type': 'cross_specific'}
        if not buy and cross_val == 1:
            pnl_pt = (entry_price - close_j) / PT_SIZE
            return {'exit_line': exit_line_name, 'exit_idx': j,
                    'bars_held': j - i, 'pnl_pt': pnl_pt, 'exit_price': close_j,
                    'exit_type': 'cross_specific'}

    return None

# ============================================================
# CERCA USCITA FISSA (TP/SL in punti)
# ============================================================
def find_exit_fixed(rows, entry, tp_pt, sl_pt, max_bars=MAX_BARS):
    i = entry['idx']
    entry_price = entry['price']
    entry_dir = entry['dir']
    buy = (entry_dir == 1)

    for j in range(i+1, min(i+max_bars, len(rows))):
        row = rows[j]
        hi, lo = float(row['high']), float(row['low'])

        if buy:
            if hi >= entry_price + tp_pt * PT_SIZE:
                pnl = tp_pt
                return {'exit_line': 'TP', 'exit_idx': j,
                        'bars_held': j - i, 'pnl_pt': pnl,
                        'exit_price': entry_price + tp_pt * PT_SIZE,
                        'exit_type': 'tp'}
            if lo <= entry_price - sl_pt * PT_SIZE:
                pnl = -sl_pt
                return {'exit_line': 'SL', 'exit_idx': j,
                        'bars_held': j - i, 'pnl_pt': pnl,
                        'exit_price': entry_price - sl_pt * PT_SIZE,
                        'exit_type': 'sl'}
        else:
            if lo <= entry_price - tp_pt * PT_SIZE:
                pnl = tp_pt
                return {'exit_line': 'TP', 'exit_idx': j,
                        'bars_held': j - i, 'pnl_pt': pnl,
                        'exit_price': entry_price - tp_pt * PT_SIZE,
                        'exit_type': 'tp'}
            if hi >= entry_price + sl_pt * PT_SIZE:
                pnl = -sl_pt
                return {'exit_line': 'SL', 'exit_idx': j,
                        'bars_held': j - i, 'pnl_pt': pnl,
                        'exit_price': entry_price + sl_pt * PT_SIZE,
                        'exit_type': 'sl'}

    return None

# ============================================================
# ANALISI 1: USCITA SUL PROSSIMO CROSSOVER (QUALSIASI LINEA)
# ============================================================
def analyze_cross_to_any(entries, rows):
    """Entry = crossover linea X direzione D, Exit = prossimo crossover qualsiasi"""
    results = []
    for ent in entries:
        ex = find_exit(rows, ent)
        if ex is None:
            continue
        results.append({
            **ent,
            **ex,
        })
    return results

# ============================================================
# ANALISI 2: USCITA SU LINEA SPECIFICA
# ============================================================
def analyze_cross_to_line(entries, rows, exit_lines=None):
    """Entry = crossover, Exit = crossover su linea specifica"""
    if exit_lines is None:
        exit_lines = LINE_NAMES
    results = []
    for ent in entries:
        for ex_line in exit_lines:
            if ex_line == ent['line']:
                continue   # skip stessa linea (gia' coperta da cross_to_any)
            ex = find_exit_on_line(rows, ent, ex_line)
            if ex is None:
                continue
            results.append({
                **ent,
                **ex,
            })
    return results

# ============================================================
# ANALISI 3: USCITA FISSA TP/SL
# ============================================================
def analyze_cross_to_fixed(entries, rows, tp_list=None, sl_list=None):
    """Entry = crossover, Exit = TP/SL fisso"""
    if tp_list is None:
        tp_list = [20, 30, 40, 50, 60, 80, 100, 120, 150]
    if sl_list is None:
        sl_list = ['MA14', 'MA30', 'MA121', 'MA365', 'Median']
    results = []

    for ent in entries:
        # SL dinamico su linea
        for sl_name in sl_list:
            try:
                sl_col = LINE_COLS[LINE_NAMES.index(sl_name)]
            except ValueError:
                continue
            row = rows[ent['idx']]
            sl_val = float(row[sl_col])
            sl_dist = abs(ent['price'] - sl_val) / PT_SIZE
            if sl_dist < 10:
                sl_dist = 1000
            # Verifica che lo SL sia dalla parte giusta
            buy = (ent['dir'] == 1)
            if buy and sl_val >= ent['price']:
                continue
            if not buy and sl_val <= ent['price']:
                continue

            for tp_pt in tp_list:
                ex = find_exit_fixed(rows, ent, tp_pt, int(sl_dist))
                if ex is None:
                    continue
                results.append({
                    **ent,
                    **ex,
                    'sl_name': sl_name,
                    'sl_dist': sl_dist,
                    'tp_pt': tp_pt,
                })
    return results

# ============================================================
# APPLICA FILTRI DI CONTESTO
# ============================================================
def filter_by_context(results, filters):
    """Filtra risultati per condizioni contestuali.
    filters: dict con 'min_<key>', 'max_<key>' per ctx fields
    """
    filtered = []
    for r in results:
        ok = True
        for key, val_range in filters.items():
            ctx_val = r['ctx'].get(key)
            if ctx_val is None:
                continue
            if 'min_' in key:
                real_key = key.replace('min_', '')
                if ctx_val < val_range:
                    ok = False
                    break
            if 'max_' in key:
                real_key = key.replace('max_', '')
                if ctx_val > val_range:
                    ok = False
                    break
        if ok:
            filtered.append(r)
    return filtered

# ============================================================
# AGGREGA E CLASSIFICA PATTERN
# ============================================================
def aggregate_patterns(results, group_keys):
    """Raggruppa per group_keys e calcola statistiche"""
    groups = defaultdict(list)
    for r in results:
        key = tuple(r.get(k) for k in group_keys)
        groups[key].append(r)

    aggregated = []
    for key, trades in groups.items():
        pnls = [t['pnl_pt'] for t in trades]
        if len(pnls) < 5:
            continue
        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls) * 100
        avg_pnl = mean(pnls)
        try:
            std_pnl = stdev(pnls) if len(pnls) > 1 else 1
        except:
            std_pnl = 1
        sharpe = (avg_pnl / std_pnl * sqrt(252)) if std_pnl > 0 else 0
        profit_factor = sum(p for p in pnls if p > 0) / max(1, abs(sum(p for p in pnls if p < 0)))
        total_pnl = sum(pnls)

        aggregated.append({
            'pattern': key,
            'trades': len(trades),
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'sharpe': sharpe,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'avg_bars': mean(t['bars_held'] for t in trades),
            'best_pnl': max(pnls),
            'worst_pnl': min(pnls),
        })

    return sorted(aggregated, key=lambda x: -x['sharpe'])

# ============================================================
# STAMPA CLASSIFICA
# ============================================================
def print_patterns(patterns, title, top=40):
    if not patterns:
        print(f"\n  Nessun pattern trovato per: {title}")
        return
    print(f"\n{'='*130}")
    print(f"  {title}")
    print(f"{'='*130}")
    headers = list(patterns[0]['pattern'])
    hdr_fmt = '  '.join(f"{{{i}:<12}}" for i in range(len(headers)))
    print(f"{'  '.join(f'{h:<12}' for h in headers)}  {'Trades':>7} {'Win%':>7} {'AvgPts':>8} {'Sharpe':>7} {'ProfitF':>8} {'TotPnl':>9} {'AvgBars':>7}")
    print('-'*130)
    for p in patterns[:top]:
        key_str = '  '.join(f"{str(k):<12}" for k in p['pattern'])
        print(f"{key_str}  {p['trades']:>7} {p['win_rate']:>6.1f}% {p['avg_pnl']:>+8.1f} {p['sharpe']:>7.2f} {p['profit_factor']:>8.2f} {p['total_pnl']:>+9.0f} {p['avg_bars']:>7.1f}")

def print_context_filters(ctx_filters):
    if not ctx_filters:
        return
    print(f"\n  Filtri contestuali attivi:")
    for k, v in ctx_filters.items():
        print(f"    {k} = {v}")

# ============================================================
# MAIN
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 pattern_mining.py <PAPP_Export.csv> [filtri...]")
        print("")
        print("Filtri opzionali (congiuntivi):")
        print("  min_cluster=X   max_cluster=X")
        print("  min_vel=X       max_vel=X")
        print("  min_vol=X       max_vol=X")
        print("  min_orderScore=X  max_orderScore=X")
        print("  min_spread=X    max_spread=X")
        print("  longBelow=1     longAbove=1")
        print("")
        print("Esempi:")
        print("  python3 pattern_mining.py PAPP_Export.csv")
        print("  python3 pattern_mining.py PAPP_Export.csv min_cluster=0 max_cluster=0.5")
        print("  python3 pattern_mining.py PAPP_Export.csv min_orderScore=2")
        print("  python3 pattern_mining.py PAPP_Export.csv longAbove=1")
        return

    path = sys.argv[1]

    # Parsing filtri
    ctx_filters = {}
    for arg in sys.argv[2:]:
        if '=' in arg:
            k, v = arg.split('=', 1)
            ctx_filters[k] = float(v) if '.' in v or 'e' in v else int(v)

    if not os.path.exists(path):
        print(f"File non trovato: {path}")
        return

    print(f"Caricamento {path}...")
    rows = load_csv(path)
    print(f"  Righe: {len(rows)}")
    if len(rows) < 50:
        print("Troppo pochi dati.")
        return
    print(f"  Date: {rows[-1]['datetime']} -> {rows[0]['datetime']}")

    # Verifica colonne
    has_cross_cols = all(cc in rows[0] for cc in CROSS_COLS)
    if not has_cross_cols:
        print("ERRORE: colonne crossover mancanti. Devi rigenerare il CSV con il nuovo Export_PAPP.mq5.")
        print(f"  Cerco: {CROSS_COLS}")
        print(f"  Trovato: {list(rows[0].keys())}")
        return

    print(f"\nRilevamento entrate (crossover direzionali)...")
    entries = detect_entries(rows)
    print(f"  Totale segnali di entrata: {len(entries)}")
    by_line = defaultdict(int)
    by_dir = defaultdict(int)
    for e in entries:
        by_line[e['line']] += 1
        by_dir['BUY' if e['dir']==1 else 'SELL'] += 1
    print(f"  Per linea:")
    for ln in LINE_NAMES:
        print(f"    {ln:<10}: {by_line[ln]:>5}")
    print(f"  BUY: {by_dir['BUY']}, SELL: {by_dir['SELL']}")

    # Applica filtri contestuali
    if ctx_filters:
        print_context_filters(ctx_filters)
        entries_f = [e for e in entries if all(
            (ctx_filters.get(f'min_{k}') is None or e['ctx'].get(k, 0) >= ctx_filters[f'min_{k}']) and
            (ctx_filters.get(f'max_{k}') is None or e['ctx'].get(k, 0) <= ctx_filters[f'max_{k}'])
            for k in ['cluster', 'vel', 'acc', 'vol', 'orderScore', 'spread', 'spreadVel', 'dMed']
        )]
        # Filtri booleani
        if 'longBelow' in ctx_filters:
            entries_f = [e for e in entries_f if e['ctx']['longBelow'] == ctx_filters['longBelow']]
        if 'longAbove' in ctx_filters:
            entries_f = [e for e in entries_f if e['ctx']['longAbove'] == ctx_filters['longAbove']]
        print(f"  Dopo filtri: {len(entries_f)} entrate")
        entries = entries_f

    if len(entries) == 0:
        print("Nessuna entrata valida.")
        return

    # ================================================================
    # ANALISI 1: CROSSOVER -> PROSSIMO CROSSOVER (qualsiasi linea)
    # ================================================================
    print(f"\n{'='*130}")
    print("  ANALISI 1: Entry = crossover linea, Exit = prossimo crossover (qualsiasi linea)")
    print(f"{'='*130}")
    res1 = analyze_cross_to_any(entries, rows)
    print(f"  Trade chiusi: {len(res1)}")
    if res1:
        p1 = aggregate_patterns(res1, ['line', 'dir'])
        print_patterns(p1, "Pattern: (entry_line, entry_dir)", top=20)

        # Per ogni entry_line, mostra le migliori uscite
        for entry_line in LINE_NAMES:
            sub = [r for r in res1 if r['line'] == entry_line]
            if len(sub) < 5:
                continue
            p_sub = aggregate_patterns(sub, ['dir', 'exit_line'])
            if p_sub and p_sub[0]['sharpe'] > 0.3:
                print_patterns(p_sub, f"  Dettaglio: entry={entry_line} (dir, exit_line)", top=10)

    # ================================================================
    # ANALISI 2: CROSSOVER -> CROSSOVER SU LINEA SPECIFICA
    # ================================================================
    print(f"\n{'='*130}")
    print("  ANALISI 2: Entry = crossover linea, Exit = crossover su linea specifica (opposta)")
    print(f"{'='*130}")
    res2 = analyze_cross_to_line(entries, rows)
    print(f"  Trade chiusi: {len(res2)}")
    if res2:
        p2 = aggregate_patterns(res2, ['line', 'dir', 'exit_line'])
        print_patterns(p2, "Pattern: (entry_line, entry_dir, exit_line)", top=30)

    # ================================================================
    # ANALISI 3: CROSSOVER -> TP/SL FISSO SU LINEA
    # ================================================================
    print(f"\n{'='*130}")
    print("  ANALISI 3: Entry = crossover, Exit = TP fisso + SL su linea")
    print(f"{'='*130}")
    res3 = analyze_cross_to_fixed(entries, rows)
    print(f"  Trade chiusi: {len(res3)}")
    if res3:
        p3 = aggregate_patterns(res3, ['line', 'dir', 'sl_name', 'tp_pt'])
        print_patterns(p3, "Pattern: (entry_line, entry_dir, sl_line, tp_pt)", top=30)

        # Miglior SL aggregato
        print(f"\n  MIGLIOR SL (media Sharpe per ogni linea SL)")
        print(f"  {'-'*60}")
        sl_perf = defaultdict(list)
        for r in res3:
            sl_perf[r['sl_name']].append(r['pnl_pt'])
        for sl, pnls in sorted(sl_perf.items(), key=lambda x: -mean(x[1]) if len(x[1])>0 else 0):
            print(f"    SL={sl:<8} -> PnL medio {mean(pnls):+.1f}  win% {sum(1 for p in pnls if p>0)/len(pnls)*100:.0f}%  (su {len(pnls)} trade)")

    # ================================================================
    # RIEPILOGO FINALE: miglior pattern per ogni entry_line
    # ================================================================
    print(f"\n{'='*130}")
    print("  RIEPILOGO: Miglior pattern per ogni linea di entrata")
    print(f"{'='*130}")

    all_results = res1 + res2 + res3
    if all_results:
        best_per_entry = defaultdict(list)
        for r in all_results:
            best_per_entry[r['line']].append(r)

        for entry_line in LINE_NAMES:
            trades = best_per_entry.get(entry_line, [])
            if len(trades) < 10:
                continue
            # Raggruppa per (dir, exit_line)
            grouped = defaultdict(list)
            for t in trades:
                key = (t['dir'], t.get('exit_line', '?'), t.get('tp_pt', 0), t.get('sl_name', ''))
                grouped[key].append(t)

            best = None
            best_sharpe = -999
            for key, ts in grouped.items():
                pnls = [t['pnl_pt'] for t in ts]
                if len(pnls) < 5:
                    continue
                avg = mean(pnls)
                try:
                    sd = stdev(pnls) if len(pnls)>1 else 1
                except:
                    sd = 1
                sh = avg/sd*sqrt(252) if sd>0 else 0
                if sh > best_sharpe:
                    best_sharpe = sh
                    best = (key, len(ts), sum(1 for p in pnls if p>0)/len(pnls)*100, avg, sh)

            if best:
                (d, ex, tp, sl), n, wr, avg, sh = best
                d_str = 'BUY' if d==1 else 'SELL'
                print(f"  {entry_line:<10} -> {d_str:<5} | exit={ex:<10} | Sharpe={sh:.2f} | Win={wr:.0f}% | Avg={avg:+.1f}pt | Trades={n}")

    print(f"\nFatto.\n")

if __name__ == '__main__':
    main()
