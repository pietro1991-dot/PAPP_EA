# USDCHF — Configurazione (rivista 2026-06-27)

Config scelta **dopo** l'analisi del blow-up del backtest precedente (−1.291 €, DD equity 89,75%,
margin call gen-2015). EA in **PIP**, indicatore `PaPP_Median` v2.02.

Questi valori sono i **default attuali** di [EA_USDCHF.mq5](EA_USDCHF.mq5).

## Cosa è cambiato e perché
Il backtest precedente è **esploso** per **impilamento illimitato** (`MaxPos=0`/`MaxPerPattern=0`):
i pattern SELL-trend (uscita su `crossMA182`, irraggiungibile in un uptrend, **senza stop**) si sono
accatastati a 22 posizioni fino al margin call. Il fix:

| | Prima (esplosa) | Ora |
|---|---|---|
| MaxPerPattern | 0 (illimitato) | **3** (impilamento controllato) |
| MaxPos | 0/20 | **6** (2 pattern × 3) |
| P3 (GRID MA14 BUY) | ON | **OFF** — perde (Ret/DD −0,92) |
| Disaster stop | — | **nessuno** (testato: peggiora, gonfia i lotti e non ferma i gap) |

## Pattern attivi
| Pattern | Entry | Dir | Exit | SL | TP | Ret/DD da solo |
|---|---|---|---|---|---|---|
| P1 | MA14 | SELL | cross MA182 | — | 500 pip | 5,46 |
| P7 | Median | SELL | cross MA182 | — | 500 pip | 3,16 |

`P3` e tutti i SELL-variant correlati: **OFF**.

## Attese (dal simulatore 1-pos / multi-pos, NON dal backtest MT5)
- P1+P7, MaxPerPattern=3, risk 4: **~+47.000 € / DD ~53% / Ret/DD ~1,30**, **niente blow-up**.
- A MaxPerPattern=1 sarebbe più sicuro (Ret/DD ~2,1) ma molto meno profitto.
- A MaxPerPattern≥5 o risk≥8 → drawdown verso 70-95% e rischio margin call: **non superare**.

## ⚠️ Avvertenze importanti
- **L'edge USDCHF è sottile**: per fare profitto serve accettare **drawdown grossi (~50%)**.
  Ret/DD ~1,3 è mediocre vs EURUSD (2,5). USDCHF resta il simbolo più debole.
- **Rischio black-swan residuo**: P1/P7 sono senza stop. Con K=3 (max 6 posizioni) un gap stile
  SNB-2015 colpirebbe meno posizioni del blow-up, ma resta esposto. Il disaster stop NON aiuta
  (i gap lo saltano e gonfia i lotti) → l'unica vera riduzione è K più basso o risk più basso.
- Numeri da **confermare col backtest MT5** (il simulatore è un'approssimazione 1-pos/multi-pos).

## File collegati
- Export: `PAPP_Export_USDCHF.csv` · Report blow-up precedente: (non archiviato, su richiesta)
