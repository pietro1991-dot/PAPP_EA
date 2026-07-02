# 09 · KPI, Budget e Funnel Math — versione abbonamento (MRR · attivazione · churn)

> "Il marketing è matematica. Se conosci i tuoi numeri, puoi comprare clienti a
> volontà." — Sabri Suby

Nel SaaS (doc 11/16) cambiano le metriche e cambia la logica del budget: non "ho
guadagnato su questa vendita?", ma **"in quanti mesi rientro del CAC?"** e **"quanto
vale il cliente nella sua vita?"**. Questo ti permette di **comprare clienti più
aggressivamente** di chi vende una tantum — un vantaggio competitivo reale.

> Valori **illustrativi** (benchmark realistici), da sostituire coi TUOI appena il
> funnel gira. Il punto non è indovinare: è misurare e migliorare l'anello debole —
> che nel SaaS spesso è **attivazione** o **churn**, non gli ads.

---

## 1. Le metriche che contano ora (per fase)
| Fase | Metrica | Target iniziale |
|---|---|---|
| Annunci | CTR / CPC | > 1,5% / 0,30–1,00 € |
| Demo/Lead | visita → lead (email) | 25–40% (CPL < 3–6 €) |
| **Conversione** | **lead → abbonato** | 1–3% (freddo), 3–8% (caldo) |
| **Conversione** | **Demo → "sblocca" (pagante)** | il KPI del prodotto-esca |
| **Attivazione ⭐** | **iscritto → EA che invia dati** | > 70% (sotto = perdi qui) |
| **Ricavo** | **MRR** e crescita % | il battito del business |
| **Ritenzione** | **Churn mensile** | < 8–10% (poi scendere) |
| **Valore** | **LTV** | > ~72 € (Bilanciato 9€ × ~8 mesi) + ascensione |
| **Efficienza** | **CAC** | ≪ LTV (obiettivo pochi €, non centinaia) |
| **Salute** | **LTV:CAC** | ≥ 3:1 |
| **Cassa** | **Payback period** | < 3–4 mesi |
| **Volume** | **n° utenti paganti** | la leva: ~12–20k per ~100k€/mese |
| **Espansione** | **ARPU** e tasso di **upsell** (EA→pacchetti) | la vera leva del LTV a questi prezzi |

## 2. Funnel Math — esempio micro-abbonamento di volume (1.000 € di ads)
Scenario prudente per leggere il modello (NON una promessa). ⚠️ Nota di realtà: con ARPU
di **pochi euro/mese**, un CPC alto **non** si ripaga in fretta → la crescita si regge su
**volume, organico e virale** (referral, contenuti), non solo su ads a pagamento.
```
Spesa ads:                       1.000 €
CPC 0,30 €      → click:          3.333
Conv. landing/Demo 30% → lead:    1.000     (CPL ≈ 1,00 €)
Conv. lead→abbonato 3%          →    30 nuovi abbonati
Attivazione 75%                →   ~22 attivi (i non-attivati → recupero/DFY)
ARPU ~7 € (mix EA 5€ + pacchetti)  → MRR aggiunto: ~ 210 €/mese ricorrenti
LTV (30 × ~7 € × ~8 mesi ≈ 56 €):  ~ 1.680 € nel tempo
CAC ≈ 1.000 / 30 ≈ 33 €  ·  Payback ≈ ~5 mesi  ·  LTV:CAC ≈ 1,7:1
```
⚠️ Scenario illustrativo: a CPC/CPL alti il payback si allunga → per reggere LTV:CAC ≥ 3:1
servono **CAC molto bassi** (organico/referral) o **ARPU più alto** (upsell ai pacchetti).
Conta IVA, fee pagamento, rimborsi, costo LLM (doc 15) nel margine vero.

> Lettura chiave: a questi prezzi il numero che comanda è il **volume** (~12–20k utenti
> paganti per ~100k€/mese) e l'**ARPU** (upsell). L'acquisizione a pagamento va tenuta
> economica; le leve principali sono **contenuti organici, referral e retention**.

## 3. Pensiero per COORTI (non per singola vendita)
- Raggruppa i clienti per **mese di acquisto** (coorte) e segui **MRR trattenuto** nel
  tempo: se la coorte di gennaio mantiene l'80% a marzo, sai quanto vale ogni nuovo cliente.
- **Net Revenue Retention**: con l'upsell (singolo→Difensivo→Bilanciato→Completo) una coorte può **crescere**
  di valore anche perdendo qualche cliente. È il sacro graal del SaaS — e a questi prezzi è **la** leva.

## 4. Budget per fasi di crescita
| Fase | Spesa ads/mese | Obiettivo | Focus |
|---|---|---|---|
| **0 — Validazione** | 300–1.000 € | 1 esca + 1 angolo che convertono; **attivazione > 70%** | Trova il messaggio E sistema l'install |
| **1 — Ottimizzazione** | 1.000–3.000 € | CAC < LTV/3, **churn < 10%** | A/B test Demo/sales/email; lifecycle |
| **2 — Scalata** | 3.000–10.000 €+ | MRR su, ROAS/payback stabili | Nuovi canali, lookalike, referral |

> Regola di Sabri adattata: **non scalare un funnel che perde all'attivazione o al
> churn.** Versare benzina su un secchio bucato accelera solo la perdita.

## 5. La sequenza di lancio (primi 90 giorni)
| Settimane | Cosa | Risultato |
|---|---|---|
| 1–2 | Dominio/HTTPS, sito, **Demo**, checkout+licenze (già pronti), tracciamento (incl. evento attivazione) | Infrastruttura |
| 3–4 | Esca (Demo+report+quiz), **3 sequenze email**, sales page+VSL | Funnel completo |
| 5–6 | Lancio soft 300–500 €/mese, 3 angoli → spingi alla **Demo** | Primi abbonati + dati attivazione |
| 7–8 | Analizza: dov'è il buco? (ads / conversione / **attivazione** / churn) → aggiusta l'anello debole | CAC/attivazione sotto controllo |
| 9–12 | Scala il budget, attiva **retention + referral + upsell** | MRR in crescita composta |

## 6. Cruscotto settimanale
- Ads: spesa, CTR, CPC, CPL per angolo.
- Conversione: lead, **Demo→pagante**, nuovi abbonati, CAC.
- **MRR**: nuovo, da espansione (upsell), perso (churn) → MRR netto.
- **Attivazione**: % iscritti con EA che invia dati (+ quanti recuperati col DFY/email).
- **Churn** e **motivi** (dato dal win-back).
- Email: open/click per step delle 3 sequenze.
- **Anello più debole della settimana** → priorità.

## 7. Leve per migliorare ogni numero
- **CTR basso** → hook/creatività (doc 06).
- **Demo→pagante basso** → offerta, garanzia, prova nella sales page (doc 03/08).
- **Attivazione bassa** → onboarding, guida "5 min", DFY, email di recupero (doc 07/14).
- **Churn alto** → lifecycle, valore a mercato fermo, upsell ai pacchetti (doc 07/16).
- **CAC alto** → a questi prezzi è fatale: privilegia organico/referral e migliora le conversioni a valle *prima* di toccare gli ads.
- **LTV/ARPU basso** → rafforza ascensione (EA→Difensivo→Bilanciato→Completo) e referral.

## 8. Strumenti di misura
GA4 + Meta Pixel + evento **attivazione** ("primo dato EA"); report nativi dell'email;
un foglio settimanale con MRR/CAC/churn/attivazione è sufficiente all'inizio. Non serve
uno stack complesso: serve **guardare i numeri ogni settimana e agire sull'anello debole**.

---

### Collegato a
- Le fasi del funnel → [05_FUNNEL_PIPELINE.md](05_FUNNEL_PIPELINE.md)
- Modello/piani → [11_MODELLO_BUSINESS.md](11_MODELLO_BUSINESS.md) · Lente SaaS → [16_STRATEGIA_RIVISTA_SAAS.md](16_STRATEGIA_RIVISTA_SAAS.md)
- Costo LLM nel margine → [15_SCALABILITA_LLM_ASSISTENTE.md](15_SCALABILITA_LLM_ASSISTENTE.md)
