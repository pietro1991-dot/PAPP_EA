#!/usr/bin/env python3
"""
line_forward.py - Ogni linea feature PRESA DA SOLA: predice la direzione del prezzo?

Per ciascuna delle 5 linee dell'indicatore (Cluster, Velocita'-con-segno,
Accel-con-segno, Volatilita', MEDIA) e per l'oscillatore distanza-mediana,
misura il rendimento di prezzo FUTURO CON SEGNO quando la linea e' ALTA (>80)
o BASSA (<20), su orizzonti D1, con split train/test.

Edge direzionale di una singola linea = quando ALTA (o BASSA) il prezzo va
sistematicamente in una direzione, stesso segno su train E test, sopra il costo.

Usa l'export D1 (cluPct/velPct/accPct/volPct reali + vel% segno + dMed%).
Uso: python3 line_forward.py <PAPP_Export.csv> [--spread-pip=1.5]
"""
import argparse
import numpy as np
import pandas as pd

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--spread-pip", type=float, default=1.5)
    ap.add_argument("--train-pct", type=float, default=0.70)
    ap.add_argument("--horizons", default="1,5,10,20")
    return ap.parse_args()

def main():
    a = parse_args()
    H = [int(x) for x in a.horizons.split(",")]
    df = pd.read_csv(a.csv)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("datetime").reset_index(drop=True)
    pip = 0.0001
    c = df["close"].to_numpy(); n = len(df)

    fwd = {h: np.concatenate([(c[h:]-c[:-h])/pip, np.full(h, np.nan)]) for h in H}

    cluP = df["cluPct"].to_numpy(); velP = df["velPct"].to_numpy()
    accP = df["accPct"].to_numpy(); volP = df["volPct"].to_numpy()
    sgnV = np.sign(df["vel%"].to_numpy())
    sgnA = np.sign(df["acc%"].to_numpy()) if "acc%" in df.columns else np.zeros(n)
    dMed = df["dMed%"].to_numpy()

    # linee come PLOTTATE (0..100). vel/accel con segno attorno a 50.
    lines = {
        "Cluster":     cluP*100,
        "Velocita":    50 + sgnV*velP*50,
        "Accel":       50 + sgnA*accP*50,
        "Volatilita":  volP*100,
        "MEDIA":       np.nanmean(np.vstack([cluP,velP,accP,volP]),axis=0)*100,
    }
    # oscillatore distanza-mediana (percentile con segno su 252 D1)
    W=252; osc=np.full(n,np.nan)
    for i in range(n):
        lo=max(0,i-W+1); w=dMed[lo:i+1]; w=w[~np.isnan(w)]
        if len(w)>=30: osc[i]=100*(w<=dMed[i]).mean()
    lines["DistMediana"]=osc

    split = int(n*a.train_pct); cost=a.spread_pip
    arange = np.arange(n)
    # baseline del periodo (drift) per orizzonte: media su TUTTE le barre valide
    base_tr = {}; base_te = {}
    for h in H:
        rtr = fwd[h][arange<split]; rtr=rtr[~np.isnan(rtr)]; base_tr[h]=rtr.mean()
        rte = fwd[h][arange>=split]; rte=rte[~np.isnan(rte)]; base_te[h]=rte.mean()

    def mret(mask_state, fwd_h):
        def m(idx):
            r=fwd_h[idx]; r=r[~np.isnan(r)]
            return (len(r), r.mean()) if len(r)>0 else (0,0.0)
        return m(mask_state & (arange<split)), m(mask_state & (arange>=split))

    print(f"\n=== OGNI LINEA DA SOLA (corretto per il DRIFT) | {a.csv.split('/')[-1]} ===")
    print(f"barre={n} split={split} spread={cost}pip")
    print("drift baseline (pip):", "  ".join(f"+{h}b tr{base_tr[h]:+.1f}/te{base_te[h]:+.1f}" for h in H))
    print("Valore = (rendimento dopo lo stato) MENO il drift del periodo. Edge = stesso segno train+test e |val|>spread.\n")
    for name, L in lines.items():
        print(f"  {name}:")
        for state, mask in [("ALTA(>80)", L>80), ("BASSA(<20)", L<20)]:
            cells=[]; robust=""
            for h in H:
                (ntr,mtr),(nte,mte)=mret(mask, fwd[h])
                atr=mtr-base_tr[h]; ate=mte-base_te[h]   # eccesso sul drift
                cells.append(f"+{h}b:{atr:+5.1f}/{ate:+5.1f}")
                if ntr>30 and nte>30 and np.sign(atr)==np.sign(ate) and abs(ate)>cost and abs(atr)>cost:
                    robust=" <== edge robusto"
            print(f"    {state:11s} N~{int(mask[:split].sum())}/{int(mask[split:].sum())} | "
                  + "  ".join(cells) + robust)
        print()

if __name__ == "__main__":
    main()
