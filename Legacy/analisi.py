#!/usr/bin/env python3
"""
Analisi Export PaPP v3 - Grid Search: tutte le combinazioni entry/exit line.
Legge il CSV generato da Export_PAPP.mq5, testa ogni combinazione,
trova quella col miglior Sharpe ratio.
"""
import csv, sys, os
from collections import defaultdict
from statistics import mean, stdev
from math import sqrt

PT_SIZE  = 0.00001
MAX_BARS = 200  # max barre in avanti per TP/SL

# ============================================================
# CARICA CSV
# ============================================================
def load_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))

# ============================================================
# SIMULA TRADE SINGOLO
# ============================================================
def simulate(rows, i, buy, sl_pt, tp_pt):
    entry = float(rows[i]['close'])
    for j in range(i+1, min(i+MAX_BARS, len(rows))):
        hi, lo = float(rows[j]['high']), float(rows[j]['low'])
        if (buy and hi >= entry + tp_pt * PT_SIZE) or (not buy and lo <= entry - tp_pt * PT_SIZE):
            return tp_pt, 'TP'
        if (buy and lo <= entry - sl_pt * PT_SIZE) or (not buy and hi >= entry + sl_pt * PT_SIZE):
            return -sl_pt, 'SL'
    return None

# ============================================================
# GRID SEARCH
# ============================================================
def grid_search(rows):
    # Linee disponibili
    ma_cols = {'MA3': 'MA3', 'MA7': 'MA7', 'MA14': 'MA14',
               'MA30': 'MA30', 'MA121': 'MA121', 'MA182': 'MA182', 'MA365': 'MA365',
               'Median': 'median'}
    # SL linee candidate
    sl_candidates = ['MA14', 'MA30', 'MA121', 'MA365', 'Median']
    # TP in punti fissi
    tp_candidates = [20, 25, 30, 35, 40, 50, 60, 80, 100, 120, 150]
    # Entry pairs: (MA_lunga, MA_corta)
    entry_pairs = [
        (365, 3, "MA365+MA3"), (365, 7, "MA365+MA7"), (365, 14, "MA365+MA14"),
        (182, 3, "MA182+MA3"), (182, 7, "MA182+MA7"), (182, 14, "MA182+MA14"),
        (121, 3, "MA121+MA3"), (121, 7, "MA121+MA7"), (121, 14, "MA121+MA14"),
        (30,  3, "MA30+MA3"),  (30,  7, "MA30+MA7"),
        (14,  3, "MA14+MA3"),
    ]
    # Bonus: singola linea
    single_lines = ['MA3', 'MA7', 'MA14', 'MA30', 'MA121', 'MA365', 'Median']
    for sl in single_lines:
        entry_pairs.append((None, sl, sl))

    results = []
    total = len(entry_pairs) * len(sl_candidates) * len(tp_candidates)
    done = 0

    for long_per, short_name, pair_name in entry_pairs:
        short_col = ma_cols.get(short_name, short_name)
        long_col = f"MA{long_per}" if long_per else short_col

        for sl_name in sl_candidates:
            for tp_pt in tp_candidates:
                done += 1
                if done % 100 == 0:
                    print(f"  Progresso: {done}/{total}")

                trades = []  # (pnl_pt, result)
                for i in range(len(rows)-1):
                    r = rows[i]
                    cls = float(r['close'])

                    if long_per is not None:  # coppia
                        lv = float(r[long_col])
                        sv = float(r[short_col])
                        buy_ok  = cls > lv and cls > sv
                        sell_ok = cls < lv and cls < sv
                    else:  # singola linea
                        sv = float(r[short_col])
                        buy_ok  = cls > sv
                        sell_ok = cls < sv

                    for buy, ok in [(True, buy_ok), (False, sell_ok)]:
                        if not ok:
                            continue

                        # SL distance
                        if sl_name == 'Median':
                            sl_val = float(r['median'])
                        else:
                            sl_val = float(r[sl_name])
                        sl_dist = abs(cls - sl_val) / PT_SIZE
                        if sl_dist < 10:
                            sl_dist = 1000

                        if buy and sl_val >= cls:
                            continue
                        if not buy and sl_val <= cls:
                            continue

                        t = simulate(rows, i, buy, sl_dist, tp_pt)
                        if t:
                            trades.append(t)

                if len(trades) < 10:
                    continue

                pnls = [t[0] for t in trades]
                wins = sum(1 for p in pnls if p > 0)
                win_rate = wins / len(pnls) * 100
                avg_pnl = mean(pnls)
                try:
                    std_pnl = stdev(pnls)
                except:
                    std_pnl = 1
                sharpe = (mean(pnls) / std_pnl * sqrt(252)) if std_pnl > 0 else 0
                profit_factor = sum(p for p in pnls if p > 0) / max(1, abs(sum(p for p in pnls if p < 0)))

                results.append({
                    'entry': pair_name,
                    'sl': sl_name,
                    'tp': tp_pt,
                    'trades': len(trades),
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'sharpe': sharpe,
                    'profit_factor': profit_factor,
                    'total_pnl': sum(pnls),
                })

    return results

# ============================================================
# STAMPA CLASSIFICA
# ============================================================
def print_rankings(results, top=30):
    if not results:
        print("\nNessuna combinazione valida trovata.")
        return

    # Per ogni entry pair, trova la combinazione migliore
    best_per_entry = defaultdict(list)
    for r in results:
        best_per_entry[r['entry']].append(r)

    print("\n" + "="*120)
    print("  MIGLIORI COMBINAZIONI (per Sharpe)")
    print("="*120)
    print(f"{'Entry':<16} {'SL':<8} {'TP':>5} {'Trades':>8} {'Win%':>7} {'AvgPts':>8} {'Sharpe':>8} {'ProfitF':>8} {'TotPnl':>10}")
    print("-"*120)

    ranked = sorted(results, key=lambda x: -x['sharpe'])
    for r in ranked[:top]:
        print(f"{r['entry']:<16} {r['sl']:<8} {r['tp']:>5} {r['trades']:>8} {r['win_rate']:>6.1f}% {r['avg_pnl']:>+7.1f} {r['sharpe']:>7.2f} {r['profit_factor']:>7.2f} {r['total_pnl']:>+9.0f}")

    print("-"*120)

    # Riepilogo: miglior entry per ogni SL+TP
    print("\n\n  TOP 5 COMBINAZIONI (per entry)")
    print("="*120)
    for entry, combos in sorted(best_per_entry.items()):
        best = max(combos, key=lambda x: x['sharpe'])
        if best['sharpe'] < 0.5:
            continue
        print(f"{entry:<14} → SL={best['sl']:<6} TP={best['tp']:>4}  Sharpe={best['sharpe']:.2f}  Win={best['win_rate']:.0f}%  Trades={best['trades']}")

    # Miglior SL aggregato (media Sharpe per ogni SL)
    print("\n\n  MIGLIOR SL (media Sharpe su tutte le entry)")
    print("-"*60)
    sl_perf = defaultdict(list)
    for r in results:
        sl_perf[r['sl']].append(r['sharpe'])
    for sl, shs in sorted(sl_perf.items(), key=lambda x: -mean(x[1])):
        print(f"  SL={sl:<8} → Sharpe medio {mean(shs):.2f}  (su {len(shs)} combinazioni)")

    # Miglior TP aggregato
    print("\n\n  MIGLIOR TP (media Sharpe su tutte le entry)")
    print("-"*60)
    tp_perf = defaultdict(list)
    for r in results:
        tp_perf[r['tp']].append(r['sharpe'])
    for tp, shs in sorted(tp_perf.items(), key=lambda x: -mean(x[1])):
        print(f"  TP={tp:<4}pt → Sharpe medio {mean(shs):.2f}  (su {len(shs)} combinazioni)")

# ============================================================
# MAIN
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 analisi.py <PAPP_Export.csv>")
        return

    path = sys.argv[1]
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

    print("\nEseguo grid search...")
    results = grid_search(rows)
    print(f"  Combinazioni valide trovate: {len(results)}")

    print_rankings(results, top=40)

    print("\nFatto.\n")

if __name__ == '__main__':
    main()
