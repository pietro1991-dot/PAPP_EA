#!/usr/bin/env python3
"""
Analisi a SINGOLO strumento: stagionalita' (ora-del-giorno, giorno-settimana) e
struttura di volatilita' su EURUSD, dal parquet di M1LOG.

Idea: i RITORNI sono ~martingala (non prevedibili in direzione), ma due strutture
a singolo strumento sono reali nel forex e NON sono predizione di direzione:
  - DRIFT stagionale per ora/giorno (microstruttura/liquidita' di sessione)
  - VOLATILITA' per ora/giorno (clustering: prevedibile, utile per sizing/timing)

Rigore:
  - log-ritorni per barra M1
  - split train/test (--split-date) per verificare la STABILITA' del drift
  - test del nulla con permutazione per il MAX |t| sulle 24 ore (controllo
    multiple-testing family-wise): un'ora "significativa" deve battere il max che
    il caso produce su 24 confronti.

Nota onesta: il drift orario, anche se reale, di solito NON sopravvive ai costi
(operare ogni ora = costi enormi). Il valore pratico maggiore e' la struttura di
VOLATILITA' (quando conviene operare / sizing), non il drift come alpha diretto.

ATTENZIONE fuso: gli orari sono in SERVER TIME del broker (vedi META). Con
MetaQuotes-Demo nel tester l'offset GMT puo' essere 0. Il PATTERN (quali ore)
e' valido; l'etichetta di sessione (Londra/NY) dipende dal fuso.

Uso:
  python3 analyze_seasonality.py <m1log.parquet> [--split-date=2018-01-01] [--nperm=200]
"""
import sys, argparse
import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet")
    ap.add_argument("--split-date", default="2018-01-01")
    ap.add_argument("--nperm", type=int, default=200)
    args = ap.parse_args()

    import pyarrow.parquet as pq
    print(f"[seas] carico {args.parquet} ...")
    df = pq.read_table(args.parquet, columns=["datetime", "high", "low", "close"]).to_pandas()
    df["datetime"] = pd.to_datetime(df["datetime"])
    n = len(df)
    print(f"[seas] {n:,} barre M1  ({df['datetime'].min()} -> {df['datetime'].max()})")

    close = df["close"].to_numpy("float64")
    ret = np.empty(n); ret[0] = np.nan
    ret[1:] = np.log(close[1:] / close[:-1]) * 100.0          # log-ritorno % per barra
    rng_pct = (df["high"].to_numpy("float64") - df["low"].to_numpy("float64")) / close * 100.0

    hour = df["datetime"].dt.hour.to_numpy()
    wday = df["datetime"].dt.weekday.to_numpy()                # 0=lun .. 6=dom
    split = pd.Timestamp(args.split_date)
    is_tr = (df["datetime"] < split).to_numpy()

    valid = np.isfinite(ret)
    r = ret[valid]; h = hour[valid]; w = wday[valid]; tr = is_tr[valid]; rg = rng_pct[valid]

    def by_group(gids, ngroups, mask=None):
        rr = r if mask is None else r[mask]
        gg = gids if mask is None else gids[mask]
        cnt = np.bincount(gg, minlength=ngroups).astype(float)
        s   = np.bincount(gg, weights=rr, minlength=ngroups)
        s2  = np.bincount(gg, weights=rr * rr, minlength=ngroups)
        mean = np.where(cnt > 0, s / cnt, 0.0)
        var  = np.where(cnt > 1, (s2 - cnt * mean * mean) / (cnt - 1), 0.0)
        std  = np.sqrt(np.maximum(var, 0))
        se   = np.where(cnt > 0, std / np.sqrt(np.maximum(cnt, 1)), np.inf)
        t    = np.where(se > 0, mean / se, 0.0)
        return cnt, mean, std, t

    # ---------- DRIFT per ORA (train) + stabilita' test + null ----------
    print("\n" + "=" * 78)
    print("DRIFT per ORA-DEL-GIORNO  (log-ritorno % medio per barra M1)")
    print("=" * 78)
    cnt_tr, mean_tr, std_tr, t_tr = by_group(h, 24, tr)
    cnt_te, mean_te, _, t_te = by_group(h, 24, ~tr)

    # null family-wise: permuta i ritorni, calcola il max|t| sulle 24 ore (train)
    rng_ = np.random.default_rng(0)
    r_tr = r[tr]; h_tr = h[tr]
    cnt_full = np.bincount(h_tr, minlength=24).astype(float)
    maxt_null = []
    for _ in range(args.nperm):
        rp = rng_.permutation(r_tr)
        s = np.bincount(h_tr, weights=rp, minlength=24)
        s2 = np.bincount(h_tr, weights=rp * rp, minlength=24)
        m = np.where(cnt_full > 0, s / cnt_full, 0)
        v = np.where(cnt_full > 1, (s2 - cnt_full * m * m) / (cnt_full - 1), 0)
        se = np.sqrt(np.maximum(v, 0)) / np.sqrt(np.maximum(cnt_full, 1))
        tt = np.where(se > 0, np.abs(m / se), 0)
        maxt_null.append(tt.max())
    thr95 = float(np.percentile(maxt_null, 95))
    print(f"Soglia |t| family-wise (95% del max su 24 ore, {args.nperm} permut.): {thr95:.2f}")
    print(f"{'ora':>3} {'n_tr':>9} {'driftTr%':>10} {'t_tr':>7} {'driftTe%':>10} {'stab':>5} {'volTr%':>8}")
    sig = []
    for hh in range(24):
        stab = "ok" if (mean_tr[hh] * mean_te[hh] > 0) else "-"     # stesso segno OOS
        flag = " <==SIG" if (abs(t_tr[hh]) > thr95 and mean_tr[hh] * mean_te[hh] > 0) else ""
        if flag: sig.append(hh)
        print(f"{hh:>3} {int(cnt_tr[hh]):>9} {mean_tr[hh]*1e4:>10.2f} {t_tr[hh]:>7.2f} "
              f"{mean_te[hh]*1e4:>10.2f} {stab:>5} {std_tr[hh]:>8.4f}{flag}")
    print("(drift in 1e-4 % per barra. SIG = |t|>soglia E stesso segno in test)")
    print(f">>> ore SIGNIFICATIVE e stabili: {sig if sig else 'NESSUNA'}")

    # ---------- VOLATILITA' per ORA ----------
    print("\n" + "=" * 78)
    print("VOLATILITA' per ORA  (dev.std ritorni M1, train) + range medio")
    print("=" * 78)
    order = np.argsort(-std_tr)
    print(f"{'ora':>3} {'volTr%':>9} {'rank':>5}")
    for hh in order[:8]:
        print(f"{hh:>3} {std_tr[hh]:>9.4f}  alta")
    for hh in order[-4:]:
        print(f"{hh:>3} {std_tr[hh]:>9.4f}  bassa")

    # ---------- DRIFT per GIORNO-SETTIMANA ----------
    print("\n" + "=" * 78)
    print("DRIFT per GIORNO-SETTIMANA (0=lun..4=ven)")
    print("=" * 78)
    cnt_w, mean_w, std_w, t_w = by_group(w, 7, tr)
    cnt_wte, mean_wte, _, _ = by_group(w, 7, ~tr)
    names = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    print(f"{'gg':>4} {'n_tr':>9} {'driftTr%':>10} {'t_tr':>7} {'driftTe%':>10} {'stab':>5} {'volTr%':>8}")
    for d in range(7):
        if cnt_w[d] == 0: continue
        stab = "ok" if mean_w[d] * mean_wte[d] > 0 else "-"
        print(f"{names[d]:>4} {int(cnt_w[d]):>9} {mean_w[d]*1e4:>10.2f} {t_w[d]:>7.2f} "
              f"{mean_wte[d]*1e4:>10.2f} {stab:>5} {std_w[d]:>8.4f}")

    print("\nNB: il DRIFT orario, anche se 'significativo', va pesato contro i costi")
    print("    (operare a ogni ora = costi enormi). La struttura di VOLATILITA' e' la")
    print("    parte piu' robusta e utile (sizing / quando operare).")


if __name__ == "__main__":
    main()
