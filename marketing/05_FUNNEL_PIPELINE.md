# 05 · Il Funnel e la Pipeline operativa

> "Non vendi a freddo. Porti uno sconosciuto in un viaggio: da 'chi sei?' a
> 'prendi i miei soldi'." — Sabri Suby

Questo documento è la **macchina completa**: ogni fase, gli strumenti, e la
pipeline operativa per costruirla e gestirla. È l'attuazione della "Halo Strategy"
del doc 01.

---

## 1. Mappa del funnel (vista d'insieme)

```
                    ┌─────────────────────────────────────────────┐
   FASE 1           │   TRAFFICO FREDDO (annunci che danno valore) │
   Traffico         │   Meta · YouTube · Google · TikTok           │ → doc 06
                    └───────────────────────┬─────────────────────┘
                                            ▼
   FASE 2           ┌─────────────────────────────────────────────┐
   Lead             │   LANDING HVCO  →  email (lead acquisito)    │ → doc 04
                    │   + Demo dashboard read-only                 │
                    └───────────────────────┬─────────────────────┘
                                            ▼
   FASE 3           ┌─────────────────────────────────────────────┐
   Nurture          │   SEQUENZA EMAIL (valore→storia→prove→       │ → doc 07
                    │   obiezioni→offerta)                         │
                    └───────────────────────┬─────────────────────┘
                                            ▼
   FASE 4           ┌─────────────────────────────────────────────┐
   Vendita          │   VSL + SALES PAGE  →  GODFATHER OFFER       │ → doc 03/08
                    │   checkout (Lifetime 997€ / Mensile 97€)     │
                    └───────────────────────┬─────────────────────┘
                                            ▼
   FASE 5           ┌─────────────────────────────────────────────┐
   Ascensione       │   Upsell: Setup DFY · PHAI Pro · Community   │ → doc 03 §7
                    └─────────────────────────────────────────────┘

   In parallelo: RETARGETING su chi non converte ad ogni fase.
```

## 2. Le 5 fasi nel dettaglio

### Fase 1 — Traffico (freddo → tiepido)
- **Canali**: Meta Ads (FB/IG) e YouTube come primari; Google Search per la
  domanda consapevole ("expert advisor MT5", "robot forex"); TikTok per volume e
  pubblico giovane.
- **Angolo**: gli annunci NON vendono l'EA. Offrono l'HVCO gratis (doc 04) o
  portano a un contenuto di valore (video).
- **Asset**: 3–5 varianti di annuncio per i 3 sotto-avatar (doc 02 §8).

### Fase 2 — Conversione a lead
- **Landing HVCO** (doc 04 §4): un obiettivo, zero distrazioni.
- **Strumento**: page builder + email/CRM (vedi §4).
- **Doppio step opzionale**: dopo l'email, invito alla **Demo read-only** della
  dashboard → i lead che vedono il prodotto convertono molto di più.

### Fase 3 — Nurture (il "Magic Lantern")
- 5–7 email in 7–10 giorni (doc 07): prima valore, poi storia, poi prove
  (storico/backtest), poi obiezioni, poi offerta.
- In parallelo: **retargeting** con contenuti/testimonianze.

### Fase 4 — Conversione a cliente
- **VSL** (video sales letter) + **sales page** lunga (doc 08) con la Godfather
  Offer (doc 03).
- **Checkout**: due opzioni (Lifetime/Mensile). Order bump (es. guida sizing) e
  upsell post-acquisto.

### Fase 5 — Ascensione & retention
- Upsell immediato (Setup DFY) in pagina di ringraziamento.
- Onboarding curato (la prima esperienza decide il rimborso o il passaparola).
- Email ricorrenti di valore → upgrade a PHAI Pro, community, referral.

## 3. Pipeline operativa — cosa costruire, in ordine
Checklist di implementazione (dipendenze dall'alto verso il basso):

1. **Dominio + HTTPS** (`app.phai.io`, wildcard cert) — sblocca PWA/notifiche.
2. **Sito/landing**: home + landing HVCO + sales page + grazie + checkout.
3. **HVCO prodotto**: report PDF + video + (demo read-only collegata all'app).
4. **CRM/email** configurato con la sequenza nurture (doc 07) e i tag.
5. **Checkout & licenze**: pagamento (Stripe) → generazione **license key**
   monouso → accesso app. (La logica licenze esiste già nell'app.)
6. **Tracciamento**: pixel Meta, tag Google/GA4, eventi (lead, checkout, acquisto).
7. **Annunci** (doc 06) caricati con creatività per i 3 sotto-avatar.
8. **Retargeting** impostato su ogni fase.
9. **Dashboard KPI** (doc 09) per leggere i numeri e iterare.

## 4. Stack strumenti consigliato (lean, sostenibile)
| Funzione | Opzione consigliata | Alternativa economica |
|---|---|---|
| Landing/sales page | Framer / Webflow / pagina nel nostro stack | Carrd |
| Email/CRM + automazioni | Brevo / MailerLite | ActiveCampaign (più potente) |
| Pagamenti + abbonamenti | Stripe | Paddle (gestisce tasse/IVA come merchant of record) |
| Licenze | logica già nell'app (license key) | Gumroad (se vuoi marketplace) |
| Video VSL | hosting su YouTube unlisted / Vimeo | self-host |
| Analytics | GA4 + Meta Pixel | Plausible (privacy-friendly) |
| Hosting app | la VPS attuale (+ dominio/cert) | — |

> **Nota fiscale**: vendendo "in giro per il mondo" l'IVA digitale è complessa.
> **Paddle** (merchant of record) la gestisce per te ed è spesso la scelta più
> semplice per un prodotto SaaS venduto a privati in più Paesi.

## 5. Tracciamento eventi (minimo indispensabile)
- `view_landing` → `lead` (opt-in) → `view_sales` → `begin_checkout` →
  `purchase` → `upsell_purchase`.
- Su Meta: eventi standard `Lead`, `InitiateCheckout`, `Purchase` (con valore).
- Serve per ottimizzare gli annunci sulle **conversioni reali**, non sui click.

## 6. La regola d'oro della pipeline (Sabri)
> **"Misura tutto. Il marketing è matematica."** Ogni fase ha un tasso di
> conversione. Migliora l'anello più debole, non quello che ti diverte di più.
> I numeri target e la "funnel math" sono nel doc 09.

---

### Collegato a
- Creatività e copy per la Fase 1 → [06_COPY_ANNUNCI.md](06_COPY_ANNUNCI.md)
- Email per la Fase 3 → [07_EMAIL_SEQUENCE.md](07_EMAIL_SEQUENCE.md)
- Numeri e budget → [09_KPI_BUDGET_PIPELINE.md](09_KPI_BUDGET_PIPELINE.md)
