# PHAI Scalping — Motore intraday (M5)

Terzo motore, per il segmento **micro-conto / abbonamento piccolo** (l'idea €3 EA + €5 assistente).
Obiettivo: uno scalp su **M5** che riusa **le linee PHAI** senza reinventarle.

## L'idea chiave (perché è fatta bene)
Il tuo sistema **ancora già le linee al D1** (`PaPP_Median` calcola le MA su D1 e le proietta su
qualunque timeframe). Quindi "le mie linee su M5" = **linee D1 (significato intatto: struttura vera)
campionate su barre M5**. È l'approccio **multi-timeframe** giusto:

- **Linee D1 = la mappa / i livelli** (dove sta il prezzo rispetto alla struttura).
- **M5 = solo il timing d'ingresso** (entri quando il prezzo M5 tocca/rompe una tua linea D1).

Calcolare le MA *native su M5* (MA365 = 365×5min ≈ 30 ore) sarebbe l'opposto: le linee perdono
significato e annegano nei costi. Quindi **NON** lo facciamo.

## Il muro da battere: i costi
Su M5 lo spread (~15 punti) è il 20-40% del movimento. **Regola:** una figura vale solo se ha
edge-per-trade **nettamente sopra il costo, fuori campione**. Se non lo mostra → lo scalping non è
per noi, e lo diciamo (onesti). Ecco perché prima si **misura**, poi si scrive l'EA.

---

## 1) Scaricare i dati (quello che ti serve ORA)

**File:** [`Export_Scalp.mq5`](Export_Scalp.mq5) — è uno **script** MT5. Per ogni barra M5 esporta:
`OHLC, spread, le 8 linee D1 (median+MA), distanza del prezzo da ogni linea (punti),
cross M5 vs ogni linea, ADX/+DI/-DI, ATR, ora, sessione`.

Passi (una volta):
1. **Indicatore**: copia `Motore base _linea-prezzo/Indicatore/PaPP_Median.ex5` (o `.mq5` da
   ricompilare con F7) in `MQL5/Indicators/` del terminale.
2. **Script**: copia `scalping/Export_Scalp.mq5` in `MQL5/Scripts/`, aprilo in MetaEditor, **F7** per
   compilare.
3. In MT5 apri un grafico **EURUSD, timeframe M5**.
4. **Carica storia M5**: Strumenti → Opzioni → Grafici → *Max barre nel grafico = Illimitato*; poi
   scrolla indietro (Home ripetuto) finché carica gli anni che vuoi (la storia M5 dipende dal broker;
   IC Markets di solito ha diversi anni).
5. Trascina `Export_Scalp` sul grafico. Imposta `InpStartDate`/`InpEndDate` e `InpFileName`
   (es. `scalp_EURUSD_M5.csv`). OK.
6. Il CSV finisce in `MQL5/Files/`. **Copialo in `scalping/data/`** del repo.

> Ripeti per **GBPUSD M5** (secondo strumento a spread stretto) se vuoi il confronto.

---

## 2) La ricerca (dopo che i dati sono in `scalping/data/`)
Riuso il tuo metodo (train/test 2020, test del nulla, spread incluso). In `scalping/ricerca/`:
1. **impulse_map su M5**: il cross M5 vs le linee D1 predice *continuazione* o *inversione*, a quali
   orizzonti, e **sopra il costo**? (segnale puro, esente da uscita → dice subito se c'è carne).
2. **squeeze/breakout su M5** dai livelli D1 (compressione tra le linee → espansione).
3. **ADX come filtro condizionante** (à la `line_feat_combo`): separa i buoni dai cattivi o è
   ridondante? *(ricorda: ADX aiuta il momentum, uccide la reversione — dipende dalla natura).*
4. Selezione strumento/sessione: gli scalp funzionano spesso solo in certe sessioni (Londra/NY).

Output atteso: **o** una figura con edge > costo OOS (→ passo 3), **o** la prova onesta che su M5
non regge (→ si sale a M15/H1, o si vira su "coaching+segnali+paper" come discusso).

---

## 3) L'EA (DOPO la validazione — non prima)
Scriverlo ora sarebbe logica finta. Quando il passo 2 conferma un edge, l'EA scalp riuserà **tutto il
plumbing esistente** degli EA del Motore Base (`EA_EURUSD.mq5`): licenza/config/telemetria/coda ordini
(`papp_push.mqh`), unità in pip. Cambia solo la logica d'ingresso (cross M5 vs linea D1 + filtro
ADX/sessione + SL/TP stretti scalp). Consegna prevista: `scalping/EA_Scalp.mq5`.

## Indicatore per il grafico
Non serve un nuovo file per *vedere* le linee su M5: attacca **`PaPP_Median`** (le tue linee) e
**`PaPP_ADX`** (già in `Motore base _linea-prezzo/Indicatore/`) a un grafico M5. L'export usa gli
stessi valori.

---

---

## RISULTATI DELLA RICERCA (2026-07-01)

**Scalping veloce (M5): BOCCIATO.** Su 16 mesi M5, ogni figura meccanizzata con le linee
e' morta, dopo costo:
- **Segui il cross** (momentum): lordo ~0, netto −12. Il cross non da' la direzione (come su D1).
- **Squeeze→breakout**: netto −13/−20, t≈−3 (significativo). I breakout su M5 *rientrano*.
- **Fade overextension veloce**: niente a 15-30 min.
Conclusione: su M5 domina costo+microstruttura. Non c'e' scalp. → sonde in `ricerca/probe_*.py`.

**Reversione swing (H1): TROVATO e VALIDATO.** Su EUR/USD H1 16 anni (2010-2026, split 2020):
fade dell'iper-estensione dalla **Median**, uscita al ritorno a osc=50, hold ~1-2 giorni.
- TEST **PF 1.25-1.31 anche a costo 25pt**, ~80 trade/anno, quasi ogni anno positivo, 27/54 config robuste.
- Meglio dell'EURGBP (PF 1.17) e piu' attivo del D1. → `ricerca/backtest_reversion.py`.
- ⚠️ E' REVERSIONE, non scalping: l'edge vive a ore/giorni, non a minuti.

**EA:** [`EA_ReversioneMajors_H1.mq5`](EA_ReversioneMajors_H1.mq5) — stessa meccanica di
`EA_RelVal`, riferimento = distanza dalla Median, TF H1. Parametri validati (PctWindow=300,
5/95, ExitLevel=50, MaxHold=48). Riusa sizing, vol-targeting e telemetria.

### Come provarlo (validazione finale)
1. `PaPP_Median.ex5` in `MQL5/Indicators`, `papp_push.mqh` in `MQL5/Include`.
2. `EA_ReversioneMajors_H1.mq5` in `MQL5/Experts`, **F7**.
3. **Strategy Tester** su EUR/USD, timeframe H1, 2010→oggi, "Every tick". Deve avvicinarsi al
   Python (PF ~1.3). Se diverge molto → debug (spread reale, esecuzione).

### Stato
- [x] Export M5/H1 + dati in `data/`
- [x] Ricerca: scalping M5 bocciato, reversione H1 validata (`ricerca/`)
- [x] `EA_ReversioneMajors_H1.mq5` (EUR/USD)
- [ ] Backtest dell'EA nel Strategy Tester (conferma che il live ≈ Python)
- [ ] Validare GBP/USD + USD/CHF H1 → portfolio 3 majors
