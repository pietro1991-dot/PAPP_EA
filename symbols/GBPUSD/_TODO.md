# GBPUSD — da completare

Scheletro pronto. Passi per attivare il simbolo (vedi README principale):

- [ ] **1. Esporta dati**: `src/scripts/Export_PAPP` su grafico **GBPUSD D1** in MT5.
      Copia `PAPP_Export.csv` da `MQL5/Files` in questa cartella.
- [ ] **2. Valida i pattern** (walk-forward + costi):
      ```
      cd symbols/GBPUSD
      python3 ../../src/analysis/pattern_mining.py PAPP_Export.csv \
              --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
      ```
      ⚠️ Lo spread di GBPUSD è più alto di EURUSD: valuta `--spread=20` o più.
- [ ] **3. Imposta i pattern** validati OOS in `EA_GBPUSD.mq5` (ora sono placeholder EURUSD).
- [ ] **4. Compila e backtesta** in MT5 sul grafico GBPUSD.

File atteso in questa cartella a fine lavoro:
`EA_GBPUSD.mq5` (+.ex5), `PAPP_Export.csv`, `analisi_oos.txt`
