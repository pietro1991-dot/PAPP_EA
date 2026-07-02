# Portafoglio Consigliato — 3 EA

I 3 EA da far girare **insieme, sullo stesso conto**. Combinati, il drawdown
scende molto sotto quello dei singoli (correlazioni ~0 tra loro).

## I 3 EA (con gli input GIÀ impostati sui valori validati)

| File | Simbolo | Motore | Input chiave (già di default) | Backtest 16y |
|------|---------|--------|-------------------------------|--------------|
| `EA_EURUSD.mq5` | **EUR/USD** H1/D1 | Base (trend) | RiskPct 12 · P1–P6 ON · P7–P8 OFF | +922% · DD 19.5% · PF 2.34 |
| `EA_RelVal_EURGBP.mq5` | **EUR/GBP** | Reversione | PctCapitale 25 · 10/90 · VolTarget ON | +110% · DD 21% · PF 1.25 |
| `EA_RelVal_GBPCHF.mq5` | **GBP/CHF** | Reversione | PctCapitale 25 · 10/90 · VolTarget ON | +258% · DD 54% |

> **Non serve cambiare nessun input**: i default nei file sono già quelli validati.

## Risultato del portafoglio (misurato dai backtest reali)

Facendo girare i 3 insieme, size validate invariate:

- **Capitale UGUALE (33/33/33)**: CAGR ~10.3% · **DD ~15.1%**
- **Pesi RISK-PARITY (consigliato)**: CAGR ~10.2% · **DD ~11.5%** ← quasi metà DD

I tre guadagnano in momenti scollegati (correlazioni mensili ~0.00), quindi il DD
combinato è molto sotto quello di GBP/CHF da solo (54%).

### Pesi risk-parity (quota di capitale — il più volatile pesa meno)

Si imposta con l'input **`QuotaConto`** (un solo conto, size validate intatte):

| EA | Size validata (non toccare) | **QuotaConto** | Su 10.000 € |
|----|------------------------------|----------------|-------------|
| EA_RelVal_EURGBP | PctCapitale 25 | **42** | 4.200 € |
| EA_EURUSD | RiskPct 12 | **38** | 3.800 € |
| EA_RelVal_GBPCHF | PctCapitale 25 | **20** | 2.000 € |

`QuotaConto` = % del conto che l'EA può usare. Siccome è % del balance vivo, il
portafoglio **compounda e si ribilancia da solo** — niente ribilanciamento manuale.
Per la versione ancora più stabile (DD ~10.3%) vedi `Portafoglio_Core_5EA` (5 EA).

## Installazione (MetaTrader 5)

1. Copia i tre `.mq5` in `MQL5/Experts/` e **ricompila (F7)** — hanno il nuovo input `QuotaConto`.
2. **Dipendenze obbligatorie** (già usate dagli altri EA del progetto):
   - `PaPP_Median.ex5` in `MQL5/Indicators/`
   - `papp_push.mqh` in `MQL5/Include/`
3. In MetaEditor apri ogni `.mq5` e premi **F7** per (ri)compilare.
4. Trascina ogni EA sul grafico del **suo** simbolo:
   - EA_EURUSD → grafico **EUR/USD**
   - EA_RelVal_EURGBP → grafico **EUR/GBP**
   - EA_RelVal_GBPCHF → grafico **GBP/CHF**
5. Lascia gli input ai default (già validati). Abilita "AutoTrading".

## Regole d'oro

- **Stesso conto** per tutti e 3 (così condividono il capitale e la
  diversificazione funziona).
- **Non toccare le size** (PctCapitale 25 / RiskPct 12): sono quelle dei backtest.
- Il "peso" di ciascuno si regola con **quanto capitale** ci metti dietro, non
  cambiando gli input.

---
*Cosa NON aggiungere: la reversione sui majors (EUR/USD, GBP/USD, USD/CHF su H1)
è stata testata e bocciata (a costo reale perde). Restano fuori dal portafoglio.*
