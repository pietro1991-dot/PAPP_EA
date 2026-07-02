# Singoli — EA venduti uno alla volta (conto dedicato)

Gli stessi 5 EA dei portafogli, ma pensati per girare **da soli su un conto dedicato**:
`QuotaConto = 100` → ogni EA usa **tutto** il capitale del conto (non una fetta).

> Codice identico agli EA dei pacchetti (stesse modifiche). Cambia **solo** la quota:
> pacchetto = frazione del conto · singolo = 100%.

| EA | File | Simbolo | Motore | Size validata (non toccare) | DD singolo |
|----|------|---------|--------|------------------------------|-----------|
| EUR/USD | `EA_EURUSD.mq5` | EUR/USD | Base (trend) | RiskPct 12 | ~20% 🟢 |
| GBP/USD | `EA_GBPUSD.mq5` | GBP/USD | Base (trend) | RiskPct 7 | ~64% 🔴 |
| USD/CHF | `EA_USDCHF.mq5` | USD/CHF | Base (trend) | RiskPct 4 | alto 🟡 |
| EUR/GBP | `EA_RelVal_EURGBP.mq5` | EUR/GBP | Reversione | PctCapitale 25 | ~21% 🟢 |
| GBP/CHF | `EA_RelVal_GBPCHF.mq5` | GBP/CHF | Reversione | PctCapitale 25 | ~54% 🔴 |

## ⚠️ Avvertenza da mostrare al cliente
Da soli, questi EA hanno **drawdown più alti** rispetto ai portafogli (i DD dei singoli
non si compensano). EUR/USD ed EUR/GBP sono i più adatti all'uso singolo; GBP/USD,
USD/CHF e GBP/CHF rendono meglio **dentro un portafoglio**. Vedi `PORTAFOGLI_EA.md`.

## Installazione
1. Copia il `.mq5` in `MQL5/Experts/` e **ricompila (F7)** (i `.ex5` vanno rigenerati).
2. Dipendenze: `PaPP_Median.ex5` in `MQL5/Indicators/`, `papp_push.mqh` in `MQL5/Include/`.
3. Metti l'EA sul grafico del suo simbolo. `QuotaConto` resta 100 (conto dedicato).
