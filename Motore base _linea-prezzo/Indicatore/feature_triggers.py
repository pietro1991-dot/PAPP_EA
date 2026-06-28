#!/usr/bin/env python3
"""
feature_triggers.py - Validazione TRIGGER AUTONOMI sulle feature di mercato PaPP.

Idea: non filtrare i crossover (lo fa gia' pattern_mining.py), ma far generare
l'entrata DIRETTAMENTE alle dinamiche delle feature (Cluster/Vel/Accel/Vol),
come gli archetipi A (trend-follow), B (fade) e C (squeeze breakout).

Per ogni trigger misura il rendimento FUTURO direzionale a +1/+3/+5/+10 barre D1,
con split temporale train(70%)/test(30%) per smascherare l'overfitting.
Un trigger e' credibile solo se l'edge regge ANCHE nel test e dopo lo spread.

Uso:
  python3 feature_triggers.py PAPP_Export.csv [--spread-pip=1.5] [--horizons=1,3,5,10]

Colonne usate dal CSV (gia' presenti in Export_PAPP):
  close, vel% (signed), acc% (signed), cluPct, velPct, accPct, volPct (percentili 0..1)
"""
import sys, argparse
import numpy as np
import pandas as pd

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--spread-pip", type=float, default=1.5, help="costo round-trip in pip")
    ap.add_argument("--horizons", default="1,3,5,10")
    ap.add_argument("--train-pct", type=float, default=0.70)
    ap.add_argument("--min-trades", type=int, default=25)
    return ap.parse_args()

def main():
    a = parse_args()
    H = [int(x) for x in a.horizons.split(",")]
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)

    pip = 0.0001                      # EURUSD/GBPUSD 5-decimali: 1 pip = 0.0001
    close = df["close"].to_numpy()
    n = len(df)

    # Rendimenti futuri in pip (entrata a close della barra-segnale, uscita a close[t+h])
    fwd = {}
    for h in H:
        f = np.full(n, np.nan)
        f[:n-h] = (close[h:] - close[:n-h]) / pip
        fwd[h] = f

    vels = df["vel%"].to_numpy()      # signed: >0 struttura sale
    accs = df["acc%"].to_numpy()      # signed

    # Percentili: usa le colonne dell'export se presenti (EURUSD nuovo),
    # altrimenti li ricostruisce dai valori grezzi replicando l'indicatore:
    # frazione dei valori <= corrente sulla finestra trailing CLWIN=252 barre D1
    # (magnitudine per vel/acc, come fa l'indicatore). GBP/CHF = export vecchi.
    CLWIN = 252
    def rolling_pct(vals, use_abs):
        x = np.abs(vals) if use_abs else vals.astype(float)
        out = np.full(len(x), np.nan)
        for i in range(len(x)):
            lo = max(0, i - CLWIN + 1)
            w = x[lo:i+1]
            w = w[~np.isnan(w)]
            if len(w) >= 30:
                out[i] = (w <= x[i]).mean()
        return out

    if "cluPct" in df.columns:
        cluP = df["cluPct"].to_numpy(); velP = df["velPct"].to_numpy()
        accP = df["accPct"].to_numpy(); volP = df["volPct"].to_numpy()
        print("[percentili: colonne export]")
    else:
        cluP = rolling_pct(df["cluster%"].to_numpy(), False)
        velP = rolling_pct(vels, True)
        accP = rolling_pct(accs, True)
        volP = rolling_pct(df["vol%"].to_numpy(), False)
        print("[percentili: ricostruiti in Python da valori grezzi, finestra 252]")

    sgnV = np.sign(vels)
    sgnA = np.sign(accs)
    # variazioni rispetto alla barra precedente (no look-ahead)
    sgnV_prev = np.concatenate([[0], sgnV[:-1]])
    sgnA_prev = np.concatenate([[0], sgnA[:-1]])
    cluP_prev = np.concatenate([[np.nan], cluP[:-1]])
    cluP_prev2 = np.concatenate([[np.nan, np.nan], cluP[:-2]])
    volP_prev = np.concatenate([[np.nan], volP[:-1]])

    # ---- Definizione trigger: ritornano array 'dir' in {-1,0,+1} ----
    triggers = {}

    # Direzione "grezza" della struttura (benchmark trend puro)
    triggers["TREND_dir(sgnVel)"] = sgnV.copy()

    # --- REVERSIONE: fade della direzione della struttura ---
    triggers["FADE_dir(-sgnVel)"] = -sgnV
    # Fade SOLO quando la struttura e' molto estesa (velocita' intensa)
    dF1 = np.zeros(n); dF1[velP > 0.70] = -sgnV[velP > 0.70]; triggers["FADE_velP>.7"] = dF1
    dF2 = np.zeros(n); dF2[velP > 0.85] = -sgnV[velP > 0.85]; triggers["FADE_velP>.85"] = dF2
    # Fade quando il ventaglio e' molto aperto (cluster esteso)
    dF3 = np.zeros(n); dF3[cluP > 0.80] = -sgnV[cluP > 0.80]; triggers["FADE_cluP>.8"] = dF3
    # Fade quando estesa E in decelerazione (struttura che sta girando)
    dF4 = np.zeros(n)
    m4 = (velP > 0.70) & (np.sign(accs) != sgnV)
    dF4[m4] = -sgnV[m4]; triggers["FADE_velP>.7&decel"] = dF4

    # A) Trend-follow: Velocita' incrocia 0 (=50) verso l'alto/basso + cluster in espansione
    velCrossUp   = (sgnV > 0) & (sgnV_prev <= 0)
    velCrossDown = (sgnV < 0) & (sgnV_prev >= 0)
    cluExpand = cluP > cluP_prev
    dA = np.zeros(n)
    dA[velCrossUp   & cluExpand & (cluP > 0.40)] = +1
    dA[velCrossDown & cluExpand & (cluP > 0.40)] = -1
    triggers["A_trendfollow(velCross+cluExp>0.4)"] = dA

    # A2) versione senza filtro cluster (solo cross di velocita')
    dA2 = np.zeros(n)
    dA2[velCrossUp]   = +1
    dA2[velCrossDown] = -1
    triggers["A2_velCross_puro"] = dA2

    # B) Fade: velocita' intensa + accelerazione CONTRO (decel) + ventaglio estremo
    decel_up   = (sgnV > 0) & (sgnA < 0)   # sale ma decelera -> fade short
    decel_down = (sgnV < 0) & (sgnA > 0)   # scende ma decelera -> fade long
    extreme = (velP > 0.80) & (cluP > 0.80)
    dB = np.zeros(n)
    dB[extreme & decel_up]   = -1
    dB[extreme & decel_down] = +1
    triggers["B_fade(velP>.8&cluP>.8&decel)"] = dB

    # B2) Fade piu' largo (solo intensita' velocita' estrema + decel)
    dB2 = np.zeros(n)
    dB2[(velP > 0.80) & decel_up]   = -1
    dB2[(velP > 0.80) & decel_down] = +1
    triggers["B2_fade(velP>.8&decel)"] = dB2

    # C) Squeeze breakout: compressione (cluP basso) che inizia ad aprirsi + vol in salita
    squeeze_prev = cluP_prev < 0.20
    opening = cluP > cluP_prev
    volUp = volP > volP_prev
    dC = np.zeros(n)
    dC[squeeze_prev & opening & volUp & (sgnV > 0)] = +1
    dC[squeeze_prev & opening & volUp & (sgnV < 0)] = -1
    triggers["C_squeeze(cluP<.2->apre&volUp)"] = dC

    # C2) Accelerazione che gira (early trend) col segno dell'accel
    accCrossUp   = (sgnA > 0) & (sgnA_prev <= 0)
    accCrossDown = (sgnA < 0) & (sgnA_prev >= 0)
    dC2 = np.zeros(n)
    dC2[accCrossUp]   = +1
    dC2[accCrossDown] = -1
    triggers["C2_accelCross_puro"] = dC2

    # ====== IDEE NUOVE: distanza-dal-centro (esaurimento) + incroci linee ======
    velP_prev = np.concatenate([[np.nan], velP[:-1]])
    accP_prev = np.concatenate([[np.nan], accP[:-1]])
    volP_prev = np.concatenate([[np.nan], volP[:-1]])
    avg = np.nanmean(np.vstack([cluP, velP, accP, volP]), axis=0)   # linea MEDIA (0..1)
    avg_prev = np.concatenate([[np.nan], avg[:-1]])

    # 1) ESAURIMENTO velocita': era estesa (>0.8) e ora l'intensita' RITORNA verso il centro -> fade
    exhV = (velP_prev >= 0.80) & (velP < velP_prev)
    dE = np.zeros(n); dE[exhV] = -sgnV[exhV]; triggers["EXH_vel(>.8 e rientra)->fade"] = dE
    # 2) ESAURIMENTO accel: accel intensa che rientra, struttura in salita/discesa -> fade
    exhA = (accP_prev >= 0.80) & (accP < accP_prev)
    dEA = np.zeros(n); dEA[exhA] = -sgnV[exhA]; triggers["EXH_acc(>.8 e rientra)->fade"] = dEA

    # 3) INCROCIO Volatilita' x Cluster = accensione regime; direzione dal segno Vel
    volCrossClu = (volP > cluP) & (volP_prev <= cluP_prev)
    dX1 = np.zeros(n); dX1[volCrossClu] = sgnV[volCrossClu];  triggers["X_volXclu->segui"] = dX1
    dX2 = np.zeros(n); dX2[volCrossClu] = -sgnV[volCrossClu]; triggers["X_volXclu->fade"]  = dX2

    # 4) INCROCIO Velocita'-intensita' x MEDIA = momentum che supera il regime medio
    velCrossAvg = (velP > avg) & (velP_prev <= avg_prev)
    dX3 = np.zeros(n); dX3[velCrossAvg] = sgnV[velCrossAvg];  triggers["X_velXmedia->segui"] = dX3
    dX4 = np.zeros(n); dX4[velCrossAvg] = -sgnV[velCrossAvg]; triggers["X_velXmedia->fade"]  = dX4

    # 5) DISTANZA della MEDIA dal centro: regime estremo (avg alto = molto stress) -> fade struttura
    dD = np.zeros(n); hi_avg = avg > 0.70; dD[hi_avg] = -sgnV[hi_avg]; triggers["MEDIA>.7->fade"] = dD

    # 6) MEDIA come interruttore di regime (dal risultato: alta-MEDIA = trend, bassa = reversione)
    calm = avg < 0.30
    stress = avg > 0.70
    dC1 = np.zeros(n); dC1[calm]   = -sgnV[calm];   triggers["REG_calmo(MEDIA<.3)->fade"]   = dC1
    dC2 = np.zeros(n); dC2[stress] = +sgnV[stress]; triggers["REG_stress(MEDIA>.7)->segui"] = dC2

    # ---- Valutazione ----
    split = int(n * a.train_pct)
    cost = a.spread_pip

    def stats(dirarr, h, lo, hi):
        idx = np.arange(lo, hi)
        d = dirarr[idx]
        r = fwd[h][idx]
        m = (d != 0) & ~np.isnan(r)
        d, r = d[m], r[m]
        if len(d) == 0:
            return None
        net = d * r - cost            # rendimento direzionale al netto spread
        N = len(net)
        mean = net.mean()
        sd = net.std(ddof=1) if N > 1 else 0.0
        t = mean / (sd / np.sqrt(N)) if sd > 0 else 0.0
        hit = (net > 0).mean()
        return dict(N=N, mean=mean, hit=hit, t=t)

    print(f"\n=== FEATURE TRIGGERS | {a.csv} ===")
    print(f"barre={n}  train=0..{split}  test={split}..{n}  spread={cost}pip\n")
    print("Per ciascun trigger: TRAIN e TEST -> N trade, media pip/trade (netto), hit%, t-stat")
    print("Edge credibile = stesso segno su train E test, |t|>=2, e media netta > 0.\n")

    for h in H:
        print(f"\n################  ORIZZONTE +{h} barre D1  ################")
        print(f"{'trigger':40s} | {'TRAIN N/mean/hit/t':28s} | {'TEST N/mean/hit/t':28s} | verdetto")
        print("-"*120)
        rows = []
        for name, d in triggers.items():
            tr = stats(d, h, 0, split)
            te = stats(d, h, split, n)
            rows.append((name, tr, te))
        # ordina per |t| test
        def keyf(x):
            return abs(x[2]["t"]) if x[2] else 0
        rows.sort(key=keyf, reverse=True)
        for name, tr, te in rows:
            def fmt(s):
                if not s: return f"{'-':>28s}"
                return f"{s['N']:4d}/{s['mean']:+6.1f}/{s['hit']*100:4.0f}%/{s['t']:+5.2f}"
            verdict = "—"
            if tr and te and tr["N"] >= a.min_trades and te["N"] >= a.min_trades:
                same = np.sign(tr["mean"]) == np.sign(te["mean"])
                if same and te["mean"] > 0 and abs(te["t"]) >= 2 and abs(tr["t"]) >= 2:
                    verdict = "*** EDGE ROBUSTO"
                elif same and te["mean"] > 0:
                    verdict = "ok (debole)"
                elif same and te["mean"] < 0:
                    verdict = "perdente coerente"
                else:
                    verdict = "incoerente (overfit?)"
            print(f"{name:40s} | {fmt(tr):28s} | {fmt(te):28s} | {verdict}")

    # baseline non condizionato
    print("\n--- baseline non condizionato (drift medio, tutte le barre) ---")
    for h in H:
        r = fwd[h][:split]; r = r[~np.isnan(r)]
        rt = fwd[h][split:]; rt = rt[~np.isnan(rt)]
        print(f"  +{h}b: train media={r.mean():+.2f}pip  test media={rt.mean():+.2f}pip")
    print()

if __name__ == "__main__":
    main()
