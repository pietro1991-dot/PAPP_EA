#!/usr/bin/env python3
"""
m1_to_parquet.py - Convertitore LEGGERO da CSV M1 (export MT5 semplice) a parquet
per il comando `regime` di analyze_structural.py.

`regime` legge solo: datetime, high, low, close  (+ spread_pts opzionale per il
costo REALE per-barra). Questo script tiene solo quelle colonne.

CSV atteso (header): datetime,open,high,low,close[,tick_volume][,spread_pts|spread]
  datetime nel formato MT5 "YYYY.MM.DD HH:MM".

Uso:
  python3 m1_to_parquet.py EURUSD_M1.csv EURUSD_M1.parquet
"""
import sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

def main():
    if len(sys.argv) < 3:
        print("uso: python3 m1_to_parquet.py <in.csv> <out.parquet>"); sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    writer = None; total = 0
    for i, chunk in enumerate(pd.read_csv(src, chunksize=1_000_000)):
        chunk["datetime"] = pd.to_datetime(chunk["datetime"], format="%Y.%m.%d %H:%M")
        keep = ["datetime", "high", "low", "close"]
        # accetta spread reale sotto vari nomi
        for cand in ("spread_pts", "spread", "spread_points"):
            if cand in chunk.columns:
                chunk = chunk.rename(columns={cand: "spread_pts"})
                keep.append("spread_pts"); break
        for c in ("high", "low", "close"):
            chunk[c] = chunk[c].astype("float32")
        if "spread_pts" in keep:
            chunk["spread_pts"] = chunk["spread_pts"].astype("float32")
        out = chunk[keep]
        table = pa.Table.from_pandas(out, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(dst, table.schema, compression="zstd")
        writer.write_table(table)
        total += len(out); print(f"  chunk {i}: {total:,} righe")
    if writer is not None: writer.close()
    print(f"[m1->parquet] fatto: {total:,} righe -> {dst}"
          + ("  (con spread reale)" if writer and 'spread_pts' in keep else "  (senza spread: userai --cost-pips)"))

if __name__ == "__main__":
    main()
