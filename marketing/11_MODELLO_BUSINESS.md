# 11 · Modello di Business — analisi di tutti i modelli e scelta del vincente

> "Un'azienda è una macchina per convertire spesa di marketing in profitto.
> Il modello di business decide quanto vale ogni cliente che quella macchina
> produce." — principio (parafrasi di Sabri Suby)

Obiettivo di questo documento: mettere sul tavolo **tutti** i modelli di business
possibili per PHAI Trading, valutarli con criteri oggettivi, e **scegliere quello
con il miglior rapporto profitto × probabilità di successo**. Poi dettagliarlo con
prezzi, economia unitaria e piano di attivazione.

> ⚠️ Tutti i numeri sono **illustrativi** (benchmark realistici), non promesse.
> Ogni modello che tocca la performance di mercato deve rispettare il [doc 10](10_COMPLIANCE_DISCLAIMER.md).

---

## 1. I modelli candidati (gli 8 sul tavolo)

| # | Modello | In una riga |
|---|---|---|
| A | **Licenza una tantum** | Paghi 997 € una volta, software tuo per sempre |
| B | **Abbonamento SaaS** | Micro-abbonamento di volume: 4–12 €/mese per EA/pacchetto + app + AI |
| C | **Ibrido (one-time + sub)** | Lifetime a chi vuole, abbonamento come default |
| D | **Freemium** | App/EA base gratis, paghi per pro (coppie, AI, segnali) |
| E | **IB / Broker rebate** | EA economico/gratis, guadagni dal rebate sul volume tradato |
| F | **Vendita di segnali** | Abbonamento ai segnali, non al software |
| G | **White-label / licensing** | Vendi la tecnologia ad altri brand/broker |
| H | **Marketplace (MQL5)** | Vendi/affitti l'EA sullo store MQL5 |

---

## 2. La matrice di valutazione (punteggio 1–5, più alto = meglio)

Criteri pesati per ciò che conta davvero in questo business:
**Ricavo ricorrente · LTV (profitto per cliente) · Probabilità di successo /
facilità · Scalabilità mondiale · Basso rischio regolatorio · Resistenza al churn
· Adattamento al prodotto già costruito.**

| Modello | Ricorr. | LTV | Prob. successo | Scala | Basso rischio legale | Anti-churn | Fit prodotto | **TOT /35** |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A — Una tantum | 1 | 3 | 4 | 4 | 4 | 2 | 4 | **22** |
| **B — Abbonamento** | **5** | **5** | **4** | **5** | **4** | **4** | **5** | **32** |
| **C — Ibrido** | **5** | **5** | **5** | **5** | **4** | **4** | **5** | **33** |
| D — Freemium | 4 | 3 | 3 | 5 | 4 | 3 | 4 | 26 |
| E — IB rebate | 5 | 4 | 3 | 4 | 2 | 3 | 3 | 24 |
| F — Segnali | 5 | 4 | 2 | 4 | 1 | 3 | 3 | 22 |
| G — White-label | 4 | 5 | 2 | 3 | 3 | 4 | 3 | 24 |
| H — Marketplace | 3 | 2 | 4 | 3 | 4 | 2 | 2 | 20 |

**Vincitore: C — Modello Ibrido (abbonamento-first) → 33/35.**
Subito dietro, il suo stesso cuore: B (abbonamento puro, 32).

---

## 3. Analisi modello per modello (perché questi punteggi)

### A — Licenza una tantum (22)
- ✅ Cassa subito, semplice da capire, nessuna gestione di rinnovi.
- ❌ **Nessun ricorrente**: ogni mese riparti da zero a cercare clienti ("treadmill").
  LTV basso, valore aziendale basso. Il prodotto (app + AI su server) ha **costi
  ricorrenti** (VPS, LLM) che una vendita una tantum non copre nel tempo.
- Verdetto: ottimo come *opzione* (cassa + ancora di prezzo), pessimo come *unico* modello.

### B — Abbonamento SaaS (32) ⭐
- ✅ **Ricavo ricorrente prevedibile** (MRR), LTV alto, valutazione aziendale alta
  (un business SaaS vale multipli del fatturato ricorrente).
- ✅ **Copre i costi ricorrenti** del prodotto (server/AI) per definizione (costo marginale LLM ~0).
- ✅ Barriera d'ingresso **bassissima** (4 €/mese vs 997 € secchi) → **volume enorme di clienti nel mondo**.
- ✅ **Il prodotto è GIÀ costruito per questo**: SaaS su VPS, license key, AI condivisa.
- ❌ Churn: se l'utente perde sul mercato può disdire. → mitigazione nel §5.
- Verdetto: il **cuore** del business.

### C — Ibrido (33) 🏆
- = Micro-abbonamento **per-EA** come default **+** ascensione ai **pacchetti-portafoglio**
  (venduti sul drawdown basso) **+** opzione lifetime/DFY come iniezione di cassa.
- ✅ Prende il meglio di A e B: **ricorrente di volume** dalla maggioranza + **iniezioni di
  cassa** da chi vuole servizi one-time + una scala di prezzo che porta all'ARPU alto.
- ✅ Massima flessibilità per il cliente = massima conversione (più "veicoli" di
  acquisto, principio di Sabri, doc 03 §2).
- Verdetto: **la scelta.** È B reso ancora più forte.

### D — Freemium (26)
- ✅ Tantissimi utenti gratis → grande imbuto, ottimo per dati e passaparola.
- ❌ Conversione free→paid tipicamente bassa (2–5%); regalare AI/server a utenti
  gratis **brucia margine** (costi LLM/VPS reali). Rischioso da solo.
- Verdetto: **non come modello base**, ma una *demo read-only gratuita* (doc 04) dà
  il 90% del beneficio del freemium senza i costi. Da usare come acquisizione, non
  come monetizzazione.

### E — IB / Broker rebate (24)
- Meccanica: il cliente apre il conto col **tuo link broker**; tu ricevi un rebate
  per ogni lotto tradato. Puoi quasi regalare il software e monetizzare sul volume.
- ✅ Ricorrente e "passivo", può **sussidiare il CAC** (acquisisci in perdita sul
  software e recuperi sul volume).
- ❌ **Conflitto d'interessi**: guadagni di più se il cliente trada di più → incentivo
  malsano, e mina la nostra arma (la fiducia/trasparenza). ❌ Rischio regolatorio e
  reputazionale; dipendenza da un singolo broker.
- Verdetto: **possibile flusso SECONDARIO e trasparente** (vedi §6), MAI il modello
  primario, MAI nascosto al cliente.

### F — Vendita di segnali (22)
- ❌ Vendere segnali "compra/vendi" può configurarsi come **consulenza
  d'investimento regolamentata** in molte giurisdizioni → serve licenza. Alto rischio
  legale. Inoltre svilisce il prodotto (l'EA esegue da solo).
- Verdetto: **da evitare** come modello. I segnali restano una *feature* dell'app,
  non un prodotto venduto come consiglio.

### G — White-label / licensing (24)
- ✅ Pochi clienti, contratti grossi, LTV altissimo (vendi la tecnologia a un broker
  o a un brand che la rivende).
- ❌ Ciclo di vendita lungo, B2B, richiede track record e reputazione che oggi non
  hai ancora. Difficile come *partenza*.
- Verdetto: **fase 2/3** del business, dopo aver costruito brand e numeri. Non ora.

### H — Marketplace MQL5 (20)
- ✅ Facile, pubblico già pronto, gestione pagamenti inclusa.
- ❌ Commissioni alte, prezzi schiacciati verso il basso, **non puoi costruire la
  tua lista** (l'asset di Sabri), niente brand, niente app/AI valorizzati.
- Verdetto: **canale di acquisizione secondario** (vetrina + credibilità), non il
  business.

---

## 4. LA SCELTA — Modello Ibrido "abbonamento-first" con value ladder

> **PHAI Trading è un micro-abbonamento SaaS di volume** (prezzi bassi, obiettivo tanti
> utenti, disdici quando vuoi), con opzione lifetime/DFY per la cassa e una scala di
> ascensione ai pacchetti per l'ARPU/LTV. Acquisizione tramite demo gratuita (effetto
> freemium senza i costi). Eventuale flusso secondario IB **solo se trasparente**.
>
> **Nota prodotto:** niente navigazione "per motore". "Trend" e "reversione" restano solo
> come *tipo* di strategia (e come spiegazione del perché i pacchetti sono decorrelati = DD basso).
> **Segnali + assistente AI sono INCLUSI con ogni EA o pacchetto**, senza costi extra.

### I piani (proposta concreta)

| Piano | Prezzo | Cosa include | A chi |
|---|---|---|---|
| **Demo** | Gratis | Dashboard read-only con dati reali, AI a domande limitate | Acquisizione/lead (doc 04) |
| **Assistente + Segnali** | **5 €/mese** | Segnali real-time + push (entrata/TP/SL) + **AI illimitato**, senza EA | Ingresso a più bassa frizione |
| **EA singolo** | **4 €/mese** | **1 EA** a scelta (best-seller EUR/USD) + **segnali + AI inclusi** + storico/backtest | Tripwire |
| **Pacchetto Difensivo** | **7 €/mese** | 2 EA (EUR/USD + EUR/GBP), **DD ~12.5%** | Il portafoglio più tranquillo |
| **Pacchetto Bilanciato** ⭐ | **9 €/mese** | 3 EA (EUR/USD + EUR/GBP + GBP/CHF), **DD ~11.5%** — CONSIGLIATO | Il piano-cuore |
| **Pacchetto Completo** | **12 €/mese** | **Tutti e 5 gli EA** in risk-parity, **DD ~10.3%**, CAGR storico ~12%/anno, **AI premium** | Eroe: max valore, min DD |

**Ascensione (ARPU/LTV — doc 03 §8):**
- **Da 1 EA (5€) → Difensivo (7€) → Bilanciato (9€) → Completo (12€)**: il percorso naturale,
  venduto sul **drawdown che scende** (più EA decorrelati = DD più basso).
- **Setup "Fatto-Per-Te"** (broker+VPS+install): servizio opzionale, **€20 una tantum**.

> Ancoraggio (Sabri): i pacchetti si vendono sul **drawdown basso**. Mostra prima il
> **Completo (12 €, tutto, DD ~10.3%)**: dopo, il **Bilanciato 9 €** sembra ovvio, e
> **4 €** (una strategia) un no-brainer per provare.

---

## 5. Economia unitaria e perché vince (illustrativo)

### Costi ricorrenti per cliente (stima)
- Server/VPS (condiviso) + AI/LLM (modello gratuito Zen, costo marginale ~0) +
  pagamenti (~3–5% + fee fissa per transazione, che a 4-12 € **pesa in %**) → **costo
  variabile per cliente basso in assoluto**, ma la fee fissa va tenuta d'occhio a questi prezzi.
- Margine lordo su un Bilanciato a 9 €/mese: **alto** in %, ma **pochi € in assoluto** →
  il business si regge sul **volume** e sull'**ARPU** (upsell ai pacchetti), non sul per-cliente.

### Il numero che decide tutto: LTV vs CAC (e il volume)
```
Pacchetto Bilanciato 9 €/mese · permanenza media stimata 8 mesi  → LTV ≈ 72 € (solo sub)
+ ascensione al Completo / DFY                     → LTV ≈ 90–110 €
CAC obiettivo: deve restare ≪ LTV → pochi € (via organico/referral, non ads cari)
Rapporto LTV:CAC ≥ 3:1   →  sano solo se il CAC resta molto basso

Obiettivo dichiarato ~100k€/mese → servono ~12–20k utenti paganti.
La leva è VOLUME (acquisizione/retention) × ARPU (upsell pacchetti), non il prezzo alto.
```
- Con la **licenza una tantum** (A), il LTV sarebbe ~997 € *una volta* e poi stop.
- Con l'**ibrido di volume**, un cliente paga ricorrente **per mesi/anni** + sale di pacchetto
  → LTV cumulato **prevedibile**; moltiplicato per **decine di migliaia di utenti** fa il fatturato.

### Perché alta probabilità di successo
1. **Prodotto già pronto per questo modello** (zero rework: SaaS, licenze, AI).
2. **Barriera bassissima** (4 €, AI inclusa) → conversioni di volume dal traffico mondiale.
3. **Ricorrente** → ogni cliente nuovo si somma ai vecchi (crescita composta del MRR).
4. **Demo gratuita** → abbatte il rischio percepito senza bruciare margine.
5. **Trasparenza** come anti-churn e anti-truffa (il nostro differenziatore, doc 01).

### Mitigazione del churn (il rischio #1 del SaaS di trading)
- Il valore NON è solo il P&L: è **lo strumento** (app, AI, trasparenza, educazione)
  → l'utente resta anche in mesi piatti perché il tool gli serve.
- **Prezzo così basso** che disdire per risparmiare pochi euro ha poco senso → churn strutturalmente contenuto.
- Onboarding curato (doc 07) → time-to-value rapido → meno disdette precoci.
- Comunicazione onesta sui drawdown → aspettative corrette → meno rimborsi/abbandoni.

---

## 6. Il flusso secondario opzionale: IB rebate (con onestà)
Se vuoi un secondo motore di ricavo:
- Partnership con un broker seri → link IB → rebate per lotto.
- **Regola PHAI**: dichiararlo apertamente al cliente ("se apri qui, noi riceviamo
  un piccolo rebate dal broker; non aumenta i tuoi costi"). Trasparenza totale.
- Può **sussidiare il CAC**: con un rebate ricorrente puoi permetterti di acquisire
  clienti anche a margine sottile sul software, e scalare gli ads più aggressivamente.
- ❗ Non legare MAI la logica dell'EA al generare volume: distruggerebbe la fiducia
  e creerebbe rischio regolatorio. Il rebate è un effetto collaterale, non l'obiettivo.

---

## 7. Roadmap del business (fasi)
| Fase | Quando | Modello attivo | Obiettivo |
|---|---|---|---|
| **1 — Lancio** | Mesi 1–3 | Per-EA (Assistente+Segnali/singolo/Pacchetti) + Demo gratis | Validare funnel, primi MRR |
| **2 — Scala** | Mesi 4–9 | + ascensione ai pacchetti (Difensivo/Bilanciato/Completo), + DFY, + IB opz. | Crescere volume e ARPU |
| **3 — Espansione** | Mesi 10+ | + White-label/B2B, + nuove coppie/mercati, marketplace come vetrina | Grandi contratti, nuovi canali |

## 8. KPI specifici di questo modello (oltre al doc 09)
- **MRR** (ricavo ricorrente mensile) e sua **crescita %**.
- **N° utenti paganti** (la leva del modello: ~12–20k per ~100k€/mese).
- **Churn mensile** (target < 8–10% all'inizio, da abbassare).
- **LTV:CAC** ≥ 3:1 (con CAC molto basso) e **ARPU**.
- **Tasso di ascensione** (quanti clienti salgono ai pacchetti).
- **Conversione Demo→pagante**.

---

## 9. Decisione finale (riassunto)
> **Modello scelto: micro-abbonamento SaaS di volume, per-EA.**
> Abbonamento mensile (da 4 € a 12 €, disdici quando vuoi) come cuore ricorrente,
> **+** Demo gratuita come acquisizione, **+** ascensione ai pacchetti-portafoglio
> (venduti sul drawdown basso) per l'ARPU/LTV, **+** eventuale DFY/IB come flusso secondario.
> **Segnali + assistente AI inclusi in ogni EA/pacchetto.**
>
> **Perché:** massimo punteggio (33/35), massimo ricavo ricorrente, sfrutta al 100% il
> prodotto già costruito, barriera d'ingresso quasi nulla per fare **volume nel mondo**
> (obiettivo ~12–20k utenti → ~100k€/mese), e usa la trasparenza come difesa dal churn.

---

### Collegato a
- I prezzi entrano nella → [03_GODFATHER_OFFER.md](03_GODFATHER_OFFER.md)
- L'economia unitaria si misura col → [09_KPI_BUDGET_PIPELINE.md](09_KPI_BUDGET_PIPELINE.md)
- Ogni claim di performance → [10_COMPLIANCE_DISCLAIMER.md](10_COMPLIANCE_DISCLAIMER.md)
