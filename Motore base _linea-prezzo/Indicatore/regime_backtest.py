#!/usr/bin/env python3
"""
regime_backtest.py - Backtest VERO della strategia regime-gated sulle feature.

La linea MEDIA (media dei 4 percentili feature) decide il REGIME; il segno della
Velocita' mediana da' la DIREZIONE.
  - mode=fade   : entra CONTRO la struttura (dir = -segno Vel)   [EURUSD, regime calmo]
  - mode=follow : entra CON la struttura  (dir = +segno Vel)     [GBPUSD, regime stress]

Regime attivo: MEDIA < gate_lo (calmo)  oppure  MEDIA > gate_hi (stress).
Entrata: alla chiusura della barra-segnale, se flat e regime attivo e segno Vel != 0.
Uscita: regime finito  OPPURE  segno Vel si gira contro  OPPURE  max_hold  OPPURE stop.
Una posizione per volta, equity sequenziale, netto spread, split train/test.

Uso:
  python3 regime_backtest.py <csv> --mode=fade   --regime=calm   [--gate=0.30]
  python3 regime_backtest.py <csv> --mode=follow --regime=stress [--gate=0.70]
      [--max-hold=12] [--stop-pip=60] [--spread-pip=1.5] [--exit-on-velflip=1]
"""
import argparse
import numpy as np
import pandas as pd

CLWIN = 252

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--mode", choices=["fade", "follow"], required=True)
    ap.add_argument("--regime", choices=["calm", "stress"], required=True)
    ap.add_argument("--gate", type=float, default=None)
    ap.add_argument("--max-hold", type=int, default=12)
    ap.add_argument("--stop-pip", type=float, default=60)
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--exit-on-velflip", type=int, default=1)
    ap.add_argument("--hold-fixed", type=int, default=0, help="1 = esci SOLO a max_hold/stop (ignora regime-end e velflip)")
    ap.add_argument("--train-pct", type=float, default=0.70)
    return ap.parse_args()

def rolling_pct(vals, use_abs):
    x = np.abs(vals) if use_abs else vals.astype(float)
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        lo = max(0, i - CLWIN + 1)
        w = x[lo:i+1]; w = w[~np.isnan(w)]
        if len(w) >= 30:
            out[i] = (w <= x[i]).mean()
    return out

def summ(trades, start_eq=0):
    if not trades:
        return None
    p = np.array([t["pnl"] for t in trades])
    wins = p[p > 0]; losses = p[p < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() != 0 else float('inf')
    sd = p.std(ddof=1) if len(p) > 1 else 0.0
    t = p.mean()/(sd/np.sqrt(len(p))) if sd > 0 else 0.0
    eq = np.cumsum(p); dd = (eq - np.maximum.accumulate(eq)).min()
    avg_hold = np.mean([tr["hold"] for tr in trades])
    ret_dd = p.sum() / -dd if dd < 0 else float('inf')
    return dict(N=len(p), tot=p.sum(), mean=p.mean(), hit=(p>0).mean(),
                pf=pf, t=t, dd=dd, hold=avg_hold, retdd=ret_dd)

def main():
    a = parse_args()
    gate = a.gate if a.gate is not None else (0.30 if a.regime == "calm" else 0.70)
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    close = df["close"].to_numpy()
    vels = df["vel%"].to_numpy()
    sgnV = np.sign(vels)

    if "cluPct" in df.columns:
        cluP = df["cluPct"].to_numpy(); velP = df["velPct"].to_numpy()
        accP = df["accPct"].to_numpy(); volP = df["volPct"].to_numpy()
    else:
        cluP = rolling_pct(df["cluster%"].to_numpy(), False)
        velP = rolling_pct(vels, True)
        accP = rolling_pct(df["acc%"].to_numpy(), True)
        volP = rolling_pct(df["vol%"].to_numpy(), False)
    avg = np.nanmean(np.vstack([cluP, velP, accP, volP]), axis=0)   # linea MEDIA

    def in_regime(i):
        if np.isnan(avg[i]): return False
        return avg[i] < gate if a.regime == "calm" else avg[i] > gate

    sign = -1 if a.mode == "fade" else +1
    n = len(df)
    pos = 0; entry_px = 0.0; entry_i = 0; pdir = 0
    trades = []
    for i in range(n):
        if pos == 0:
            if in_regime(i) and sgnV[i] != 0:
                pos = 1; pdir = int(sign * sgnV[i]); entry_px = close[i]; entry_i = i
        else:
            move = (close[i] - entry_px) / pip * pdir
            held = i - entry_i
            hit_stop = (a.stop_pip > 0 and move <= -a.stop_pip)
            hit_time = held >= a.max_hold
            if a.hold_fixed:
                regime_end = False; velflip = False
            else:
                regime_end = not in_regime(i)
                velflip = a.exit_on_velflip and (sgnV[i] != 0) and (np.sign(sgnV[i]) == -np.sign(pdir) if a.mode=="follow" else np.sign(sgnV[i]) == np.sign(pdir))
            if regime_end or velflip or hit_stop or hit_time:
                trades.append(dict(exit_i=i, pnl=move - a.spread_pip, hold=held))
                pos = 0

    split = int(n * a.train_pct)
    tr = [t for t in trades if t["exit_i"] < split]
    te = [t for t in trades if t["exit_i"] >= split]

    print(f"\n=== REGIME BACKTEST | {a.csv.split('/')[-1]} ===")
    print(f"mode={a.mode} regime={a.regime} gate={gate} maxHold={a.max_hold} "
          f"stop={a.stop_pip} velflipExit={a.exit_on_velflip} spread={a.spread_pip}pip")
    hdr = f"{'':6s}  {'N':>4s} {'tot pip':>8s} {'media':>6s} {'hit':>5s} {'PF':>5s} {'t':>5s} {'maxDD':>7s} {'Ret/DD':>6s} {'hold':>5s}"
    print(hdr)
    for label, s in [("TRAIN", summ(tr)), ("TEST", summ(te)), ("TUTTO", summ(trades))]:
        if not s:
            print(f"  {label:6s}: nessun trade"); continue
        print(f"  {label:5s} {s['N']:5d} {s['tot']:+8.0f} {s['mean']:+6.1f} "
              f"{s['hit']*100:4.0f}% {s['pf']:5.2f} {s['t']:+5.2f} {s['dd']:+7.0f} "
              f"{s['retdd']:6.2f} {s['hold']:5.1f}")
    print()

if __name__ == "__main__":
    main()
