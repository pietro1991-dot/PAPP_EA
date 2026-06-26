# EURUSD — Perché alcuni pattern sono ON (true) e altri OFF (false)

Documento di riferimento sulla configurazione dei pattern dell'EA EURUSD
(`EA_EURUSD.mq5`). Spiega la logica dietro `InpPx_On = true/false`.

---

## 1. Configurazione attuale in sintesi

| Pattern | On | Entry (cross) | Dir | Exit | SL | TP | Famiglia |
|---|---|---|---|---|---|---|---|
| **P1** | ✅ true | MA30 | SELL | — | **MA365** (dinamico) | 150 | Analisi 3 |
| **P2** | ✅ true | MA121 | BUY | — | **MA365** (dinamico) | 150 | Analisi 3 |
| **P3** | ✅ true | MA365 | SELL | — | **MA121** (dinamico) | 120 | Analisi 3 |
| **P4** | ✅ true | MA7 | SELL | — | **MA365** (dinamico) | 120 | Analisi 3 |
| **P5** | ✅ true | MA30 | BUY | — | **MA365** (dinamico) | 150 | Analisi 3 |
| **P6** | ✅ true | MA14 | BUY | — | **MA365** (dinamico) | 150 | Analisi 3 |
| **P7** | ❌ false | MA3 | SELL | cross MA121 | **nessuno (0)** | 1500 (cap) | Analisi 2 |
| **P8** | ❌ false | MA7 | SELL | cross MA121 | **nessuno (0)** | 1500 (cap) | Analisi 2 |
| **P9** | ❌ false | MA14 | SELL | cross MA121 | **nessuno (0)** | 1500 (cap) | Analisi 2 |
| **P10** | ❌ false | MA30 | SELL | cross MA121 | **nessuno (0)** | 1500 (cap) | Analisi 2 |

**ON = P1-P6** (Analisi 3: entry cross + SL dinamico su linea + TP fisso).
**OFF = P7-P10** (Analisi 2: entry cross + exit su cross MA121, senza hard SL).

---

## 2. Il principio guida: sopravvivenza out-of-sample (OOS)

Il pattern miner ha analizzato **4278 barre D1 (2009–2026)** con **walk-forward
validation**:
- allena sui dati **fino al 2020** (train),
- valida su **dopo il 2020** (test, "out-of-sample"),
- metriche corrette: **Sharpe per-trade** (non annualizzato/gonfiato), nessun
  look-ahead, costi/spread inclusi.

**Regola d'oro:** si tengono **solo** i pattern positivi sia in train **che** in
test. I numeri spettacolari calcolati su tutto lo storico erano spesso artefatti
che **crollavano fuori campione**.

---

## 3. Le tre analisi e chi è sopravvissuto

| Analisi | Logica | Esito out-of-sample |
|---|---|---|
| **1** — entry cross → qualsiasi cross opposto | nessuna struttura di rischio | ❌ crolla (win 50%→35%, Sharpe→0/negativo) |
| **2** — entry cross → **exit su cross MA121** | trend-following, **niente hard SL** | ❌ crolla nel walk-forward (win→~36%, Sharpe→0/negativo) |
| **3** — entry cross + **SL dinamico su linea** + **TP fisso** | struttura di rischio chiusa | ✅ **l'unica che regge OOS** |

Da qui la scelta: **solo Analisi 3 entra accesa nell'EA**.

---

## 4. Perché P1-P6 sono TRUE

Sono i pattern di **Analisi 3 sopravvissuti out-of-sample**. Struttura comune:
**entry su crossover + SL dinamico su una linea lontana (di norma MA365) + TP
fisso stretto (120–150 pt)**, senza cross-exit. Vantaggi:

- **Win rate altissimo (89–98%)**: il TP stretto incassa spesso.
- **Drawdown contenuto e robustezza**: lo **SL dinamico** si trascina sulla linea
  MA ad ogni barra e protegge il profitto; validati su train *e* test.
- **Diversificazione**: mix di **SELL** (P1 MA30, P3 MA365, P4 MA7) e **BUY**
  (P2 MA121, P5 MA30, P6 MA14), su orizzonti diversi (veloci MA7/14/30 e lenti
  MA121/365). Non è la stessa scommessa ripetuta → le perdite non arrivano tutte
  nello stesso momento.

---

## 5. Perché P7-P10 sono FALSE

Sono la **famiglia Analisi 2** (entry cross → uscita su cross MA121, con un TP cap
a 1500 pt come tetto). Tenuti **spenti** per tre motivi:

1. **Niente hard SL (`SL = 0`) → gap risk.** Un gap di weekend o uno strappo
   violento può produrre una **perdita enorme senza protezione**.
2. **Drawdown grande.** Anche se il profitto cumulato OOS è alto
   (~+192k, win ~64% col cap), il profilo è **opposto** a P1-P6: pochi trade
   molto grandi, oscillazioni ampie del capitale.
3. **Validazione fragile.** Analisi 2 non supera il walk-forward standard.

Sono **lasciati nel file** (non rimossi) come **opzione attivabile**: se un giorno
si vuole aggiungere la scommessa trend-following, basta mettere `On = true` —
consapevoli del rischio di gap e del drawdown.

---

## 6. La sfumatura da non dimenticare

Anche **P1-P6 non sono privi di rischio**: lo SL su MA365 è **lontano**, quindi il
profilo è **"alto win / perdita rara ma grande"**. Quando perdono (il prezzo corre
fino a MA365), la **singola perdita è ampia**. Per questo ciò che conta di più è il
**risk management / position sizing**: il win rate alto, da solo, inganna.

---

## 7. Come validare/rivedere questa scelta

La configurazione attuale è frutto dell'analisi storica. Per confermarla con dati
*ground-truth*:

1. **Backtest MT5** dell'EA con la config attuale (P1-P6) → la tab **Storico**
   mostra performance anno per anno (spread/slippage reali del broker).
2. **Backtest di confronto** attivando P7-P10 (P1-P10) → misura *quanto* profitto
   aggiungono e a costo di *quale* drawdown, invece di deciderlo a memoria.

Confrontando i due run si decide in modo oggettivo se vale la pena accendere la
famiglia trend-following.
