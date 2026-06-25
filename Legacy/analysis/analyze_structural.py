#!/usr/bin/env python3
"""
Analisi + validazione walk-forward del sistema STRUTTURALE (linee ancorate a D1)
dal log M1LOG_<SYM>.csv prodotto da EA_Logger.mq5.

PATTERN considerati (tutti):
  - incroci PREZZO<->LINEA   (8 linee)            etype = "P:<linea>"
  - incroci LINEA<->LINEA    (28 coppie)          etype = "X:<a>_<b>"
  rilevati a risoluzione M1 (le linee evolvono intraday), con baseline
  resettata a ogni nuova D1 (lo "scalino" giornaliero non genera falsi incroci).

Per ogni evento: ritorno forward del PREZZO (close-to-close) su piu' orizzonti.

Validazione (cmd `validate`):
  - split temporale TRAIN/TEST (--split-date)
  - per ogni pattern (etype,edir [+ contesto]) la DIREZIONE del trade
    (long/short) e' scelta SOLO sul train (segno del ritorno medio train)
  - sul TEST si misura l'expectancy NETTA (costi sottratti) e il win-rate
  - "survivors" = pattern net-positivi su TRAIN *e* TEST con abbastanza trade
  Cosi' un edge finto in-sample non sopravvive.

Uso:
  python3 analyze_structural.py convert  <M1LOG.csv> <out.parquet>
  python3 analyze_structural.py analyze  <in.parquet> [--horizons=60,240,1440]
                                          [--events-out=events.parquet] [--out=report.txt]
  python3 analyze_structural.py validate <events.parquet> [--horizons=60,240,1440]
                                          [--split-date=2018-01-01] [--cost-pips=1.5]
                                          [--pip=0.0001] [--min-trades=150]
                                          [--out=valid.txt] [--grid-out=grid.csv]

Note oneste:
  - Orizzonti in BARRE M1 (tempo-mercato, salta weekend/festivi).
  - Eventi nelle ultime max(horizons) barre = forward troncato -> esclusi.
  - Expectancy per-trade indipendente (non equity sequenziale con trade
    sovrapposti): e' il primo livello di rigore, il portafoglio e' lo step dopo.
"""
import sys, argparse, itertools
import numpy as np
import pandas as pd

LEVELS = ["median", "MA365", "MA182", "MA121", "MA30", "MA14", "MA7", "MA3"]
LBL    = {"median": "M", "MA365": "365", "MA182": "182", "MA121": "121",
          "MA30": "30", "MA14": "14", "MA7": "7", "MA3": "3"}
MA7COLS = ["MA365", "MA182", "MA121", "MA30", "MA14", "MA7", "MA3"]

FLOAT_COLS = ["open", "high", "low", "close",
              "median", "MA365", "MA182", "MA121", "MA30", "MA14", "MA7", "MA3",
              "cluster", "vel", "acc", "vol", "spread", "spreadVel",
              "dMed", "d365", "d182", "d121", "d30", "d14", "d7", "d3"]


# ----------------------------------------------------------------------------
def cmd_convert(csv_path, parquet_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    print(f"[convert] {csv_path} -> {parquet_path}")
    writer = None; total = 0
    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=1_000_000)):
        chunk["datetime"] = pd.to_datetime(chunk["datetime"], format="%Y.%m.%d %H:%M")
        chunk["d1open"]   = pd.to_datetime(chunk["d1open"],   format="%Y.%m.%d %H:%M")
        for c in FLOAT_COLS:
            if c in chunk.columns:
                chunk[c] = chunk[c].astype("float32")
        chunk["tick_volume"] = chunk["tick_volume"].astype("int32")
        chunk["nBelowPrice"] = chunk["nBelowPrice"].astype("int16")
        chunk["rank"] = chunk["rank"].astype("string")
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(parquet_path, table.schema, compression="zstd")
        writer.write_table(table)
        total += len(chunk); print(f"  chunk {i}: {total:,} righe")
    if writer is not None: writer.close()
    print(f"[convert] fatto: {total:,} righe")


# ----------------------------------------------------------------------------
def _detect(close, L, day_change, n):
    """indici e direzione (+1/-1) dei cambi di segno di (close-L), no day_change."""
    side = np.where(close > L, 1, -1).astype(np.int8)
    prev = np.empty(n, np.int8); prev[0] = side[0]; prev[1:] = side[:-1]
    cross = (side != prev) & (~day_change) & (L > 0)
    idx = np.nonzero(cross)[0]
    return idx, side[idx]


def build_events(df, horizons):
    n = len(df)
    close = df["close"].to_numpy("float64")
    high  = df["high"].to_numpy("float64")
    low   = df["low"].to_numpy("float64")
    d1    = df["d1open"].to_numpy("int64")
    dc = np.empty(n, bool); dc[0] = True; dc[1:] = d1[1:] != d1[:-1]

    nbelow7 = np.zeros(n, np.int8)
    for c in MA7COLS:
        nbelow7 += (close > df[c].to_numpy("float64")).astype(np.int8)

    levarr = {name: df[name].to_numpy("float64") for name in LEVELS}

    e_idx, e_type, e_dir = [], [], []
    # prezzo <-> linea
    for name in LEVELS:
        idx, sd = _detect(close, levarr[name], dc, n)
        e_idx.append(idx); e_type.append(np.full(idx.shape, "P:" + LBL[name], object)); e_dir.append(sd)
    # linea <-> linea (28 coppie)
    for i in range(len(LEVELS)):
        for j in range(i + 1, len(LEVELS)):
            a, b = LEVELS[i], LEVELS[j]
            diff = levarr[a] - levarr[b]
            side = np.where(diff > 0, 1, -1).astype(np.int8)
            prev = np.empty(n, np.int8); prev[0] = side[0]; prev[1:] = side[:-1]
            cross = (side != prev) & (~dc) & (levarr[a] > 0) & (levarr[b] > 0)
            idx = np.nonzero(cross)[0]
            e_idx.append(idx)
            e_type.append(np.full(idx.shape, f"X:{LBL[a]}_{LBL[b]}", object))
            e_dir.append(side[idx])

    e_idx  = np.concatenate(e_idx)
    e_type = np.concatenate(e_type)
    e_dir  = np.concatenate(e_dir)
    order = np.argsort(e_idx, kind="stable")
    e_idx, e_type, e_dir = e_idx[order], e_type[order], e_dir[order]

    Hmax = max(horizons)
    valid = e_idx < (n - Hmax)
    e_idx, e_type, e_dir = e_idx[valid], e_type[valid], e_dir[valid]
    print(f"[events] {len(e_idx):,} eventi (P+X), esclusi {int((~valid).sum()):,} troncati")

    ev = pd.DataFrame({
        "idx": e_idx.astype("int64"),
        "datetime": df["datetime"].to_numpy()[e_idx],
        "etype": e_type, "edir": e_dir,
        "close": close[e_idx].astype("float32"),
        "nBelow7": nbelow7[e_idx],
        "spread": df["spread"].to_numpy()[e_idx].astype("float32"),
        "vol": df["vol"].to_numpy()[e_idx].astype("float32"),
        "cluster": df["cluster"].to_numpy()[e_idx].astype("float32"),
    })
    ev["spread_sign"] = np.where(ev["spread"] > 0, "bull", "bear")
    try:
        ev["vol_bkt"] = pd.qcut(ev["vol"], 3, labels=["lo", "mid", "hi"]).astype("string")
    except Exception:
        ev["vol_bkt"] = "na"

    for H in horizons:
        fcl = np.full(n, np.nan); fcl[:n - H] = close[H:]
        c = close[e_idx]
        ev[f"ret{H}"] = ((fcl[e_idx] - c) / c * 100.0).astype("float32")
    return ev


def cmd_analyze(parquet_path, horizons, events_out, out_path):
    import pyarrow.parquet as pq
    cols = ["datetime", "d1open", "high", "low", "close",
            "cluster", "vol", "spread", "nBelowPrice"] + LEVELS
    cols = list(dict.fromkeys(cols))
    print(f"[analyze] carico {parquet_path} ...")
    df = pq.read_table(parquet_path, columns=cols).to_pandas()
    print(f"[analyze] {len(df):,} righe")
    ev = build_events(df, horizons)
    if events_out:
        ev.to_parquet(events_out)
        print(f"[analyze] eventi salvati in {events_out}")

    lines = []
    def P(*a):
        s = " ".join(str(x) for x in a); lines.append(s); print(s)
    P("=" * 70); P("EVENTI STRUTTURALI — riepilogo"); P("=" * 70)
    P(f"Totale eventi: {len(ev):,}  ({ev['datetime'].min()} -> {ev['datetime'].max()})")
    P("\n--- conteggio per tipo evento (top 20) ---")
    vc = ev["etype"].value_counts().head(20)
    for k, v in vc.items(): P(f"  {k:<14} {v:>9,}")
    P("\nUsa `validate` per la verifica walk-forward su tutti i pattern.")
    if out_path:
        open(out_path, "w").write("\n".join(lines)); print(f"[report] salvato in {out_path}")


# ----------------------------------------------------------------------------
CONTEXT_SETS = [
    ([], "base"),
    (["spread_sign"], "+spread"),
    (["nBelow7"], "+nBelow7"),
    (["vol_bkt"], "+vol"),
    (["spread_sign", "vol_bkt"], "+spread+vol"),
]


def cmd_validate(events_path, horizons, split_date, cost_pips, pip, min_trades, out_path, grid_out,
                 shuffle_seed=0):
    print(f"[validate] carico {events_path} ...")
    ev = pd.read_parquet(events_path)
    ev["datetime"] = pd.to_datetime(ev["datetime"])
    split = pd.Timestamp(split_date)
    tr_all = ev[ev["datetime"] < split].copy()
    te_all = ev[ev["datetime"] >= split].copy()
    print(f"[validate] train {len(tr_all):,} ({ev['datetime'].min().date()}..{(split).date()})  "
          f"test {len(te_all):,} ({split.date()}..{ev['datetime'].max().date()})")
    cost_price = cost_pips * pip

    results = []
    for cset, clabel in CONTEXT_SETS:
        keys = ["etype", "edir"] + cset
        for H in horizons:
            rc = f"ret{H}"
            # --- dedup NON-overlapping (cooldown = H minuti) per pattern ---
            sub = ev[keys + ["datetime", rc, "close"]].dropna(subset=[rc])
            sub = sub.sort_values("datetime").reset_index(drop=True)
            tvals = sub["datetime"].to_numpy()
            keep = np.zeros(len(sub), bool)
            H_td = np.timedelta64(H, "m")
            for _, gi in sub.groupby(keys, observed=True).indices.items():
                last = None
                for pos in gi:                       # gi gia' ordinato per tempo
                    t = tvals[pos]
                    if last is None or (t - last) >= H_td:
                        keep[pos] = True; last = t
            sub = sub[keep]
            split_mask = sub["datetime"] < split
            tr = sub[split_mask][keys + [rc]]
            te = sub[~split_mask][keys + [rc, "close"]].copy()
            if shuffle_seed:
                # NULL: rompe il legame evento->esito permutando i ritorni nel test
                rng = np.random.default_rng(shuffle_seed * 1000 + H)
                te[rc] = rng.permutation(te[rc].to_numpy())
            gtr = tr.groupby(keys, observed=True)[rc].agg(n_tr="count", m_tr="mean").reset_index()
            gtr = gtr[gtr["n_tr"] >= min_trades]
            if gtr.empty:
                continue
            gtr["dir"] = np.sign(gtr["m_tr"]).astype(int)
            gtr = gtr[gtr["dir"] != 0]
            m = te.merge(gtr[keys + ["dir", "n_tr", "m_tr"]], on=keys, how="inner")
            if m.empty:
                continue
            m["cost"] = cost_price / m["close"] * 100.0
            m["pnl"] = m["dir"] * m[rc] - m["cost"]
            gte = m.groupby(keys + ["dir", "n_tr", "m_tr"], observed=True).agg(
                n_te=("pnl", "count"), m_te=("pnl", "mean"),
                win=("pnl", lambda x: float((x > 0).mean()))).reset_index()
            gte = gte[gte["n_te"] >= min_trades]
            if gte.empty:
                continue
            gte["H"] = H
            gte["ctx"] = clabel
            gte["pattern"] = gte.apply(
                lambda r: f"{r['etype']}|dir={int(r['edir'])}|" +
                          "|".join(f"{k}={r[k]}" for k in cset), axis=1)
            results.append(gte)

    if not results:
        print("[validate] nessun pattern con abbastanza trade."); return
    res = pd.concat(results, ignore_index=True)
    # net edge sul test = expectancy media (gia' al netto costi)
    res["edge_net"] = res["m_te"]
    res["tot_net"] = res["m_te"] * res["n_te"]            # proxy del profitto OOS totale
    res["robust"] = (res["m_tr"].abs() > 0) & (res["m_te"] > 0)  # train ha direzione, test net>0

    if grid_out:
        res.sort_values("tot_net", ascending=False).to_csv(grid_out, index=False)
        print(f"[validate] griglia completa ({len(res):,} righe) salvata in {grid_out}")

    surv = res[res["robust"]].copy()
    lines = []
    def P(*a):
        s = " ".join(str(x) for x in a); lines.append(s); print(s)

    P("=" * 96)
    P("VALIDAZIONE WALK-FORWARD — tutti i pattern (P:prezzo-linea, X:linea-linea)")
    P("=" * 96)
    P(f"Split: train < {split.date()} <= test   |  costo round-trip: {cost_pips} pip ({cost_price:.5f})")
    P(f"min trade (train & test): {min_trades}   |  orizzonti: {horizons}")
    P(f"Pattern testati: {len(res):,}   |  survivors (net>0 OOS): {len(surv):,}")
    P("")
    P("edge_net = expectancy NETTA per trade nel TEST (%)  ;  win = % trade test in profitto")
    P("dir = +1 long / -1 short (scelta SOLO sul train)")
    P("")

    if surv.empty:
        P(">>> NESSUN pattern net-positivo out-of-sample. (Nessun edge robusto: onesto.)")
    else:
        # Top per profitto OOS totale (edge * numero trade), con edge sopra-costo
        P("--- TOP 25 SURVIVORS per profitto OOS totale (edge_net x n_te) ---")
        top = surv.sort_values("tot_net", ascending=False).head(25)
        P(f"  {'pattern':<46} {'H':>5} {'n_tr':>7} {'n_te':>7} {'edge_tr%':>9} {'edge_net%':>10} {'win%':>6}")
        for _, r in top.iterrows():
            P(f"  {r['pattern']:<46} {int(r['H']):>5} {int(r['n_tr']):>7} {int(r['n_te']):>7} "
              f"{r['m_tr']*r['dir']:>9.4f} {r['edge_net']:>10.4f} {r['win']*100:>6.1f}")
        P("")
        P("--- TOP 15 SURVIVORS per edge per-trade (n_te>=" + str(max(min_trades, 300)) + ") ---")
        hi = surv[surv["n_te"] >= max(min_trades, 300)].sort_values("edge_net", ascending=False).head(15)
        P(f"  {'pattern':<46} {'H':>5} {'n_te':>7} {'edge_net%':>10} {'win%':>6}")
        for _, r in hi.iterrows():
            P(f"  {r['pattern']:<46} {int(r['H']):>5} {int(r['n_te']):>7} {r['edge_net']:>10.4f} {r['win']*100:>6.1f}")

    P("")
    P("NB: 'survivor' = direzione presa sul train, net-positivo nel test. NON e' una")
    P("    garanzia: resta il rischio di multiple-testing (molti pattern testati).")
    P("    Prossimo rigore: equity di portafoglio (no trade sovrapposti) sui survivor.")
    if out_path:
        open(out_path, "w").write("\n".join(lines)); print(f"\n[report] salvato in {out_path}")


# ----------------------------------------------------------------------------
def sltp_simulate(idx, high, low, close, tp_price, sl_price, maxbars):
    """Per ogni evento simula uscita SL/TP/time-stop per LONG e SHORT.
    Regola conservativa: se in una barra il range tocca sia SL sia TP -> SL prima.
    Ritorna pnl gross % (long,short) e indice di uscita (long,short)."""
    n = len(close)
    m = len(idx)
    pl = np.empty(m); ps = np.empty(m)
    el = np.empty(m, np.int64); es = np.empty(m, np.int64)
    for q in range(m):
        i = idx[q]; p = close[i]
        TPl = p + tp_price; SLl = p - sl_price
        TPs = p - tp_price; SLs = p + sl_price
        end = i + maxbars
        if end > n - 1: end = n - 1
        ld = False; sd = False
        lr = 0.0; sr = 0.0; lx = end; sx = end
        k = i + 1
        while k <= end:
            h = high[k]; l = low[k]
            if not ld:
                if l <= SLl and h >= TPl: lr = -sl_price; lx = k; ld = True
                elif h >= TPl:            lr =  tp_price; lx = k; ld = True
                elif l <= SLl:            lr = -sl_price; lx = k; ld = True
            if not sd:
                if h >= SLs and l <= TPs: sr = -sl_price; sx = k; sd = True
                elif l <= TPs:            sr =  tp_price; sx = k; sd = True
                elif h >= SLs:            sr = -sl_price; sx = k; sd = True
            if ld and sd: break
            k += 1
        if not ld: lr = close[end] - p; lx = end
        if not sd: sr = p - close[end]; sx = end
        pl[q] = lr / p * 100.0
        ps[q] = sr / p * 100.0
        el[q] = lx; es[q] = sx
    return pl, ps, el, es


def _cooldown_keep(entry_idx, exit_idx):
    """greedy: tiene un trade solo se inizia dopo l'uscita del precedente.
    entry_idx/exit_idx gia' ordinati per tempo."""
    keep = np.zeros(len(entry_idx), bool)
    last_exit = -1
    for j in range(len(entry_idx)):
        if entry_idx[j] > last_exit:
            keep[j] = True; last_exit = exit_idx[j]
    return keep


def sltp_validate(ev, split, min_trades, shuffle_seed=0, context_sets=None):
    """Per ogni pattern: scegli LONG/SHORT sul train (media pnl maggiore),
    applica cooldown sull'uscita scelta, valuta sul test. Ritorna DataFrame.
    NULL (shuffle_seed): permuta gli esiti pnl TRA i pattern nel test (rompe il
    legame pattern->esito; le medie di gruppo diventano casuali).
    context_sets: lista di (colonne_extra, etichetta); default CONTEXT_SETS."""
    if context_sets is None:
        context_sets = CONTEXT_SETS
    if shuffle_seed:
        ev = ev.copy()
        tmask = (ev["datetime"] >= split).to_numpy()
        src = np.nonzero(tmask)[0]
        rng = np.random.default_rng(shuffle_seed)
        perm = rng.permutation(src)
        for col in ("pnl_long", "pnl_short"):
            vals = ev[col].to_numpy().copy()
            vals[src] = vals[perm]
            ev[col] = vals
    results = []
    for cset, clabel in context_sets:
        keys = ["etype", "edir"] + cset
        for _, g in ev.groupby(keys, observed=True):
            g = g.sort_values("idx")
            tr = g[g["datetime"] < split]
            if len(tr) < min_trades:
                continue
            ml = tr["pnl_long"].mean(); ms = tr["pnl_short"].mean()
            if ml >= ms:
                side = 1; pcol = "pnl_long"; xcol = "el"
            else:
                side = -1; pcol = "pnl_short"; xcol = "es"
            ent = g["idx"].to_numpy(); ext = g[xcol].to_numpy()
            keep = _cooldown_keep(ent, ext)
            gk = g[keep]
            tr2 = gk[gk["datetime"] < split]; te2 = gk[gk["datetime"] >= split]
            if len(tr2) < min_trades or len(te2) < min_trades:
                continue
            pte = te2[pcol].to_numpy()
            results.append({
                "pattern": f"{g['etype'].iloc[0]}|dir={int(g['edir'].iloc[0])}|" +
                           "|".join(f"{k}={g[k].iloc[0]}" for k in cset),
                "ctx": clabel, "side": side,
                "n_tr": len(tr2), "n_te": len(te2),
                "edge_tr": tr2[pcol].mean(), "edge_te": pte.mean(),
                "win_te": float((pte > 0).mean()),
            })
    return pd.DataFrame(results)


def run_sltp_report(ev, high, low, close, sl_pips, tp_pips, maxbars, pip, cost_pips,
                    split, min_trades, out_path, grid_out, title, context_sets=None,
                    spread_pts=None):
    idx = ev["idx"].to_numpy("int64")
    tp_price = tp_pips * pip; sl_price = sl_pips * pip
    print(f"[sltp] simulo SL={sl_pips}p TP={tp_pips}p maxbars={maxbars} su {len(idx):,} eventi ...")
    pl, ps, el, es = sltp_simulate(idx, high, low, close, tp_price, sl_price, maxbars)
    entry = close[idx]
    if spread_pts is not None:
        # costo REALE: spread_pts in points (1 pip = 10 points su 5 cifre); round-trip = 1x spread
        point = pip / 10.0
        cpct = (spread_pts[idx] * point) / entry * 100.0
        print(f"[sltp] costo = spread REALE per-barra (mediano {np.nanmedian(spread_pts):.1f} pts)")
    else:
        cpct = (cost_pips * pip) / entry * 100.0
    ev = ev.copy()
    ev["pnl_long"] = pl - cpct
    ev["pnl_short"] = ps - cpct
    ev["el"] = el; ev["es"] = es

    res = sltp_validate(ev, split, min_trades, 0, context_sets)
    surv = res[(res["edge_tr"] > 0) & (res["edge_te"] > 0)]
    nulls = []
    for s in (1, 2, 3):
        rn = sltp_validate(ev, split, min_trades, s, context_sets)
        nulls.append(int(((rn["edge_tr"] > 0) & (rn["edge_te"] > 0)).sum()))
    lines = []
    def P(*a):
        x = " ".join(str(z) for z in a); lines.append(x); print(x)
    P("=" * 96)
    P(f"{title} — SL={sl_pips}p TP={tp_pips}p maxbars={maxbars} cost={cost_pips}p")
    P("=" * 96)
    P(f"Split: train < {split.date()} <= test | min trade {min_trades} | trade NON sovrapposti")
    P(f"Pattern testati: {len(res):,} | survivors REALI (train>0 & test>0): {len(surv):,}")
    P(f"survivors NULL (3 permutazioni): {nulls}  (media {np.mean(nulls):.0f})")
    P("")
    if not surv.empty:
        P("--- TOP 20 SURVIVORS per profitto OOS totale (edge_te x n_te) ---")
        surv = surv.assign(tot=surv["edge_te"] * surv["n_te"]).sort_values("tot", ascending=False)
        P(f"  {'pattern':<46} {'side':>4} {'n_tr':>6} {'n_te':>6} {'edgeTr%':>8} {'edgeTe%':>8} {'win%':>6}")
        for _, r in surv.head(20).iterrows():
            P(f"  {r['pattern']:<46} {r['side']:>4} {int(r['n_tr']):>6} {int(r['n_te']):>6} "
              f"{r['edge_tr']:>8.4f} {r['edge_te']:>8.4f} {r['win_te']*100:>6.1f}")
    if grid_out:
        res.to_csv(grid_out, index=False); P(f"\n[grid] {grid_out}")
    P("")
    P("VERDETTO: se survivors REALI ~ NULL -> nessun edge.")
    if out_path:
        open(out_path, "w").write("\n".join(lines)); print(f"[report] {out_path}")
    return res, surv, nulls


def cmd_sltp(m1_path, events_path, sl_pips, tp_pips, maxbars, pip, cost_pips,
             split_date, min_trades, out_path, grid_out):
    import pyarrow.parquet as pq
    print(f"[sltp] carico prezzi {m1_path} ...")
    px = pq.read_table(m1_path, columns=["high", "low", "close"]).to_pandas()
    high = px["high"].to_numpy("float64"); low = px["low"].to_numpy("float64")
    close = px["close"].to_numpy("float64")
    ev = pd.read_parquet(events_path)
    ev["datetime"] = pd.to_datetime(ev["datetime"])
    split = pd.Timestamp(split_date)
    run_sltp_report(ev, high, low, close, sl_pips, tp_pips, maxbars, pip, cost_pips,
                    split, min_trades, out_path, grid_out, "VALIDAZIONE SL/TP — INCROCI")


def cmd_states(m1_path, sl_pips, tp_pips, maxbars, pip, cost_pips,
               split_date, min_trades, out_path, grid_out):
    import pyarrow.parquet as pq
    dcols = ["d365", "d182", "d121", "d30", "d14", "d7", "d3"]
    cols = ["datetime", "d1open", "high", "low", "close", "dMed", "cluster", "vol", "spread"] + dcols
    print(f"[states] carico {m1_path} ...")
    df = pq.read_table(m1_path, columns=cols).to_pandas()
    df["datetime"] = pd.to_datetime(df["datetime"])
    n = len(df)
    high = df["high"].to_numpy("float64"); low = df["low"].to_numpy("float64")
    close = df["close"].to_numpy("float64")
    d1 = df["d1open"].to_numpy("int64")
    dc = np.empty(n, bool); dc[0] = True; dc[1:] = d1[1:] != d1[:-1]
    split = pd.Timestamp(split_date)
    train = (df["datetime"] < split).to_numpy()

    dMed = df["dMed"].to_numpy("float64")
    d365 = df["d365"].to_numpy("float64")
    clu  = df["cluster"].to_numpy("float64")
    vol  = df["vol"].to_numpy("float64")
    nbelow7 = np.zeros(n, np.int8)
    for c in dcols:
        nbelow7 += (df[c].to_numpy("float64") > 0).astype(np.int8)

    def pct(arr, q):
        return float(np.nanpercentile(arr[train], q))

    # (nome, feature, kind, soglia, daily)
    #   daily=True  -> metrica costante entro la D1 (cluster/vol): il trigger e' al
    #                  confine D1 (NON escludere day_change), e si ignora la warm-up (feat>0)
    #   daily=False -> metrica intraday (distanza/nBelow): escludi il day_change
    states = [
        ("DMEDhi", dMed, "above", pct(dMed, 90), False),
        ("DMEDlo", dMed, "below", pct(dMed, 10), False),
        ("D365hi", d365, "above", pct(d365, 90), False),
        ("D365lo", d365, "below", pct(d365, 10), False),
        ("CLUlo",  clu,  "below", pct(clu, 10), True),
        ("CLUhi",  clu,  "above", pct(clu, 90), True),
        ("VOLlo",  vol,  "below", pct(vol, 10), True),
        ("VOLhi",  vol,  "above", pct(vol, 90), True),
        ("NB0",    nbelow7.astype("float64"), "eq", 0, False),
        ("NB7",    nbelow7.astype("float64"), "eq", 7, False),
    ]

    e_idx, e_type = [], []
    for name, feat, kind, thr, daily in states:
        if kind == "above":   st = feat > thr
        elif kind == "below": st = feat < thr
        else:                 st = feat == thr
        prev = np.empty(n, bool); prev[0] = st[0]; prev[1:] = st[:-1]
        trig = st & (~prev) & np.isfinite(feat)
        if daily:
            trig &= (feat > 0)          # ignora warm-up (cluster/vol=0)
        else:
            trig &= (~dc)               # stato intraday: niente trigger al confine D1
        idx = np.nonzero(trig)[0]
        idx = idx[idx < (n - maxbars)]
        e_idx.append(idx); e_type.append(np.full(idx.shape, name, object))
        print(f"  stato {name:<7} soglia={thr:.4f}  trigger={len(idx):,}")
    e_idx = np.concatenate(e_idx); e_type = np.concatenate(e_type)
    order = np.argsort(e_idx, kind="stable")
    e_idx, e_type = e_idx[order], e_type[order]

    ev = pd.DataFrame({
        "idx": e_idx.astype("int64"),
        "datetime": df["datetime"].to_numpy()[e_idx],
        "etype": e_type, "edir": np.zeros(len(e_idx), np.int8),
        "close": close[e_idx],
        "nBelow7": nbelow7[e_idx],
        "spread": df["spread"].to_numpy()[e_idx],
        "vol": vol[e_idx],
    })
    ev["spread_sign"] = np.where(ev["spread"] > 0, "bull", "bear")
    try:
        ev["vol_bkt"] = pd.qcut(ev["vol"], 3, labels=["lo", "mid", "hi"]).astype("string")
    except Exception:
        ev["vol_bkt"] = "na"
    print(f"[states] totale trigger: {len(ev):,}")
    run_sltp_report(ev, high, low, close, sl_pips, tp_pips, maxbars, pip, cost_pips,
                    split, min_trades, out_path, grid_out, "VALIDAZIONE SL/TP — STATI")


def cmd_regime(m1_path, K, Z, sl_pips, tp_pips, maxbars, pip, cost_pips,
               split_date, min_trades, out_path, grid_out):
    """Trigger: movimento short-term vol-normalizzato (|zmove|>Z su K barre).
    Direzione (follow/fade) scelta sul train, per REGIME di volatilita' (ora).
    Ipotesi: alta vol -> momentum, bassa vol -> reversione."""
    import pyarrow.parquet as pq
    print(f"[regime] carico {m1_path} ...")
    cols = ["datetime", "high", "low", "close"]
    if "spread_pts" in pq.ParquetFile(m1_path).schema.names:
        cols.append("spread_pts")
    df = pq.read_table(m1_path, columns=cols).to_pandas()
    sp = df["spread_pts"].to_numpy("float64") if "spread_pts" in df.columns else None
    df["datetime"] = pd.to_datetime(df["datetime"])
    n = len(df)
    high = df["high"].to_numpy("float64"); low = df["low"].to_numpy("float64")
    close = df["close"].to_numpy("float64")
    logc = np.log(close)
    r = np.empty(n); r[0] = np.nan; r[1:] = logc[1:] - logc[:-1]
    d1 = pd.to_datetime(df["datetime"]).dt.floor("D").astype("int64").to_numpy()
    dc = np.empty(n, bool); dc[0] = True; dc[1:] = d1[1:] != d1[:-1]
    hour = df["datetime"].dt.hour.to_numpy()
    split = pd.Timestamp(split_date)
    train = (df["datetime"] < split).to_numpy()

    # vol di base (rolling std 1-bar, no look-ahead) e zmove su K barre
    W = 1440
    std1 = pd.Series(r).rolling(W, min_periods=300).std().shift(1).to_numpy()
    momK = np.empty(n); momK[:] = np.nan
    momK[K:] = logc[K:] - logc[:-K]
    denom = std1 * np.sqrt(K)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = momK / denom

    # regime per ora: terzili di volatilita' calcolati sul TRAIN
    hr_vol = np.array([np.nanstd(r[train & (hour == hh)]) if np.any(train & (hour == hh)) else np.nan
                       for hh in range(24)])
    order = np.argsort(np.where(np.isnan(hr_vol), 1e9, hr_vol))
    lab = {}
    for rank, hh in enumerate(order):
        lab[int(hh)] = "lo" if rank < 8 else ("mid" if rank < 16 else "hi")
    regime = np.array([lab[int(hh)] for hh in hour], dtype=object)

    # trigger: ingresso nello stato |zmove|>Z (transizione), no day_change
    e_idx, e_dir = [], []
    for sign, name in ((1, "up"), (-1, "dn")):
        st = (z > Z) if sign == 1 else (z < -Z)
        st = st & np.isfinite(z)
        prev = np.empty(n, bool); prev[0] = st[0]; prev[1:] = st[:-1]
        trig = st & (~prev) & (~dc)
        idx = np.nonzero(trig)[0]; idx = idx[idx < (n - maxbars)]
        e_idx.append(idx); e_dir.append(np.full(idx.shape, sign, np.int8))
    e_idx = np.concatenate(e_idx); e_dir = np.concatenate(e_dir)
    o = np.argsort(e_idx, kind="stable"); e_idx, e_dir = e_idx[o], e_dir[o]
    print(f"[regime] trigger movimento (K={K},Z={Z}): {len(e_idx):,}")

    ev = pd.DataFrame({
        "idx": e_idx.astype("int64"),
        "datetime": df["datetime"].to_numpy()[e_idx],
        "etype": np.full(len(e_idx), f"MOM{K}", object),
        "edir": e_dir,
        "close": close[e_idx],
        "regime": regime[e_idx],
    })
    csets = [([], "base"), (["regime"], "+regime")]
    run_sltp_report(ev, high, low, close, sl_pips, tp_pips, maxbars, pip, cost_pips,
                    split, min_trades, out_path, grid_out,
                    f"REGIME MOMENTUM/REVERSIONE (K={K} Z={Z})", csets, sp)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert"); c.add_argument("csv"); c.add_argument("parquet")
    a = sub.add_parser("analyze"); a.add_argument("parquet")
    a.add_argument("--horizons", default="60,240,1440")
    a.add_argument("--events-out", default=None); a.add_argument("--out", default=None)
    v = sub.add_parser("validate"); v.add_argument("events")
    v.add_argument("--horizons", default="60,240,1440")
    v.add_argument("--split-date", default="2018-01-01")
    v.add_argument("--cost-pips", type=float, default=1.5)
    v.add_argument("--pip", type=float, default=0.0001)
    v.add_argument("--min-trades", type=int, default=150)
    v.add_argument("--out", default=None); v.add_argument("--grid-out", default=None)
    v.add_argument("--shuffle-seed", type=int, default=0)
    s = sub.add_parser("sltp"); s.add_argument("m1parquet"); s.add_argument("events")
    s.add_argument("--sl", type=float, default=30); s.add_argument("--tp", type=float, default=30)
    s.add_argument("--maxbars", type=int, default=1440)
    s.add_argument("--pip", type=float, default=0.0001); s.add_argument("--cost-pips", type=float, default=1.5)
    s.add_argument("--split-date", default="2018-01-01"); s.add_argument("--min-trades", type=int, default=40)
    s.add_argument("--out", default=None); s.add_argument("--grid-out", default=None)
    st = sub.add_parser("states"); st.add_argument("m1parquet")
    st.add_argument("--sl", type=float, default=30); st.add_argument("--tp", type=float, default=30)
    st.add_argument("--maxbars", type=int, default=1440)
    st.add_argument("--pip", type=float, default=0.0001); st.add_argument("--cost-pips", type=float, default=1.5)
    st.add_argument("--split-date", default="2018-01-01"); st.add_argument("--min-trades", type=int, default=40)
    st.add_argument("--out", default=None); st.add_argument("--grid-out", default=None)
    rg = sub.add_parser("regime"); rg.add_argument("m1parquet")
    rg.add_argument("--K", type=int, default=15); rg.add_argument("--Z", type=float, default=2.0)
    rg.add_argument("--sl", type=float, default=15); rg.add_argument("--tp", type=float, default=15)
    rg.add_argument("--maxbars", type=int, default=240)
    rg.add_argument("--pip", type=float, default=0.0001); rg.add_argument("--cost-pips", type=float, default=1.5)
    rg.add_argument("--split-date", default="2018-01-01"); rg.add_argument("--min-trades", type=int, default=40)
    rg.add_argument("--out", default=None); rg.add_argument("--grid-out", default=None)
    args = ap.parse_args()

    if args.cmd == "convert":
        cmd_convert(args.csv, args.parquet)
    elif args.cmd == "analyze":
        hs = [int(x) for x in args.horizons.split(",") if x.strip()]
        cmd_analyze(args.parquet, hs, args.events_out, args.out)
    elif args.cmd == "validate":
        hs = [int(x) for x in args.horizons.split(",") if x.strip()]
        cmd_validate(args.events, hs, args.split_date, args.cost_pips, args.pip,
                     args.min_trades, args.out, args.grid_out, args.shuffle_seed)
    elif args.cmd == "sltp":
        cmd_sltp(args.m1parquet, args.events, args.sl, args.tp, args.maxbars, args.pip,
                 args.cost_pips, args.split_date, args.min_trades, args.out, args.grid_out)
    elif args.cmd == "states":
        cmd_states(args.m1parquet, args.sl, args.tp, args.maxbars, args.pip,
                   args.cost_pips, args.split_date, args.min_trades, args.out, args.grid_out)
    elif args.cmd == "regime":
        cmd_regime(args.m1parquet, args.K, args.Z, args.sl, args.tp, args.maxbars, args.pip,
                   args.cost_pips, args.split_date, args.min_trades, args.out, args.grid_out)


if __name__ == "__main__":
    main()
