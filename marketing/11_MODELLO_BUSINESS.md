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
| B | **Abbonamento SaaS** | Paghi 49–97 €/mese per EA + app + AI |
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
- ✅ **Copre i costi ricorrenti** del prodotto (server/AI) per definizione.
- ✅ Barriera d'ingresso bassa (49 €/mese vs 997 € secchi) → **più clienti nel mondo**.
- ✅ **Il prodotto è GIÀ costruito per questo**: SaaS su VPS, license key, AI condivisa.
- ❌ Churn: se l'utente perde sul mercato può disdire. → mitigazione nel §5.
- Verdetto: il **cuore** del business.

### C — Ibrido (33) 🏆
- = Abbonamento **per-EA** come default **+** Annuale **+** ascensione (Pacchetti/Portfolio).
- ✅ Prende il meglio di A e B: **ricorrente** dalla maggioranza + **iniezioni di
  cassa** da chi odia gli abbonamenti + ancora di prezzo che fa sembrare l'abbonamento
  un affare.
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

> **PHAI Trading è un business SaaS in abbonamento**, con un'opzione lifetime per la
> cassa e una scala di ascensione per il LTV. Acquisizione tramite demo gratuita
> (effetto freemium senza i costi). Eventuale flusso secondario IB **solo se
> trasparente**.

### I piani (proposta concreta)

| Piano | Prezzo | Cosa include | A chi |
|---|---|---|---|
| **Demo** | Gratis | Dashboard read-only con dati reali, AI a domande limitate | Acquisizione/lead (doc 04) |
| **PHAI Signals** | **37 €/mese** | Tutti i segnali (esecuzione manuale), app, AI base, notifiche | Barriera bassissima |
| **EA singolo** | **49 €/mese** | **1 EA automatico** a scelta + app + AI + storico/backtest | Tripwire |
| **Pacchetto Reversione** | **67 €/mese** | I **2 EA del Motore Reversione** (EUR/GBP, GBP/CHF) | Bundle-motore |
| **Pacchetto Base** ⭐ | **97 €/mese** | I **3 EA del Motore Base** (EUR/USD, GBP/USD, USD/CHF) | Il piano-cuore |
| **PHAI Portfolio** | **197 €/mese** | **Tutti i 5 EA**, 2 motori, AI premium, VPS, nuovi EA inclusi | Eroe/decoy |
| **Annuale Portfolio** | **1.970 €/anno** (2 mesi gratis) | Portfolio annuale | Riduce churn, anticipa cassa |

**Ascensione (LTV — doc 03 §7):**
- **Setup "Fatto-Per-Te"** (broker+VPS+install): +297 € una tantum.
- **PHAI Portfolio**: tutti gli EA + AI premium prioritaria + nuovi EA in anteprima +
  community: +30 €/mese sopra il Pro.
- **Community/coaching** premium: +497 €/anno.

> Ancoraggio (Sabri): mostra prima il **value stack ~4.500 €** e l'**Annuale**
> (doc 03). A quel punto **197 €/mese** (tutto) sembra ragionevole, **97 €** (un motore)
> facile, e **49 €** (una strategia) un
> no-brainer per provare.

---

## 5. Economia unitaria e perché vince (illustrativo)

### Costi ricorrenti per cliente (stima)
- Server/VPS (condiviso) + AI/LLM (modello gratuito Zen, costo marginale ~0) +
  pagamenti (~3–5%) → **costo variabile per cliente molto basso** (pochi €/mese).
- Margine lordo su un Pro a 97 €/mese: **molto alto** (>85–90%). È il bello del SaaS
  software: il costo non cresce quasi con i clienti.

### Il numero che decide tutto: LTV vs CAC
```
Pacchetto Base 97 €/mese · permanenza media stimata 8 mesi  → LTV ≈ 776 € (solo sub)
+ ascensione (30% prende Setup DFY 297 €)         → LTV ≈ 865 €+
CAC obiettivo (doc 09): < 250 €
Rapporto LTV:CAC ≈ 3,5 : 1   →  business sano e scalabile
```
- Con la **licenza una tantum** (A), il LTV sarebbe ~997 € *una volta* e poi stop.
- Con l'**ibrido**, un cliente paga ricorrente **per mesi/anni** + upsell → LTV
  cumulato **superiore** e, soprattutto, **prevedibile** (puoi pianificare e
  reinvestire in ads con sicurezza).

### Perché alta probabilità di successo
1. **Prodotto già pronto per questo modello** (zero rework: SaaS, licenze, AI).
2. **Barriera bassa** (49 €) → più conversioni dal traffico mondiale.
3. **Ricorrente** → ogni cliente nuovo si somma ai vecchi (crescita composta del MRR).
4. **Demo gratuita** → abbatte il rischio percepito senza bruciare margine.
5. **Trasparenza** come anti-churn e anti-truffa (il nostro differenziatore, doc 01).

### Mitigazione del churn (il rischio #1 del SaaS di trading)
- Il valore NON è solo il P&L: è **lo strumento** (app, AI, trasparenza, educazione)
  → l'utente resta anche in mesi piatti perché il tool gli serve.
- **Annuale scontato** sposta i clienti fuori dal churn mensile.
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
| **1 — Lancio** | Mesi 1–3 | Per-EA (Signals/singolo/Pacchetti/Portfolio) + Demo gratis | Validare funnel, primi MRR |
| **2 — Scala** | Mesi 4–9 | + Annuale, + ascensione (DFY/Portfolio), + IB opz. | Crescere MRR, alzare LTV |
| **3 — Espansione** | Mesi 10+ | + White-label/B2B, + nuove coppie/mercati, marketplace come vetrina | Grandi contratti, nuovi canali |

## 8. KPI specifici di questo modello (oltre al doc 09)
- **MRR** (ricavo ricorrente mensile) e sua **crescita %**.
- **Churn mensile** (target < 8–10% all'inizio, da abbassare).
- **LTV:CAC** ≥ 3:1.
- **% Annuale** sul totale (più alta = meno churn, più cassa).
- **Tasso di ascensione** (quanti clienti salgono a DFY/Portfolio).
- **Conversione Demo→pagante**.

---

## 9. Decisione finale (riassunto)
> **Modello scelto: SaaS abbonamento-first, per-EA.**
> Abbonamento mensile (da 49 € a 197 €) come cuore ricorrente, **+** Annuale
> (2 mesi gratis) per cassa e anti-churn, **+** Demo gratuita come acquisizione,
> **+** ascensione (DFY, Portfolio, community) per il LTV, **+** eventuale IB rebate
> trasparente come secondo motore.
>
> **Perché:** massimo punteggio (33/35), massimo ricavo ricorrente e LTV,
> sfrutta al 100% il prodotto già costruito, barriera d'ingresso bassa per vendere
> nel mondo, e usa la trasparenza (la nostra arma) come difesa dal churn.

---

### Collegato a
- I prezzi entrano nella → [03_GODFATHER_OFFER.md](03_GODFATHER_OFFER.md)
- L'economia unitaria si misura col → [09_KPI_BUDGET_PIPELINE.md](09_KPI_BUDGET_PIPELINE.md)
- Ogni claim di performance → [10_COMPLIANCE_DISCLAIMER.md](10_COMPLIANCE_DISCLAIMER.md)
