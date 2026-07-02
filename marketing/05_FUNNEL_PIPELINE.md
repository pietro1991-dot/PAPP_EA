# 05 · Il Funnel e la Pipeline — versione abbonamento (acquisisci → attiva → trattieni)

> "Non vendi a freddo. Porti uno sconosciuto in un viaggio: da 'chi sei?' a 'prendi i
> miei soldi' — e poi lo fai restare." — adattato da Sabri Suby

La "Halo Strategy" di Sabri (4 fasi) resta la spina dorsale, ma nel SaaS (doc 16)
**l'acquisto non è il traguardo**: dopo vengono **attivazione** (far funzionare l'EA) e
**retention** (farlo restare). Il valore di un abbonato si crea **dopo** il checkout.

---

## 1. Mappa del funnel (6 fasi)

```
                 ┌─────────────────────────────────────────────────┐
  FASE 1         │  TRAFFICO FREDDO — ads che DANNO valore          │ → doc 06
  Traffico       │  Meta · YouTube · Google · TikTok → alla DEMO    │
                 └───────────────────────┬─────────────────────────┘
                                         ▼
  FASE 2         ┌─────────────────────────────────────────────────┐
  Lead/Prova     │  DEMO read-only (hero) + Report + Quiz → email   │ → doc 04
                 └───────────────────────┬─────────────────────────┘
                                         ▼
  FASE 3         ┌─────────────────────────────────────────────────┐
  Nurture        │  SEQUENZA EMAIL (valore→storia→prove→obiezioni)  │ → doc 07
                 └───────────────────────┬─────────────────────────┘
                                         ▼
  FASE 4         ┌─────────────────────────────────────────────────┐
  Conversione    │  VSL + SALES PAGE → GODFATHER OFFER              │ → doc 03/08
                 │  Demo→ "sblocca": EA 5€ / Bilanciato 9€ / Compl.12€│
                 └───────────────────────┬─────────────────────────┘
                                         ▼
  FASE 5 ⭐      ┌─────────────────────────────────────────────────┐
  ATTIVAZIONE    │  registra → installa EA → primo dato live        │ → doc 07/14
                 │  lo SNODO CRITICO. DFY come riduttore di frizione │
                 └───────────────────────┬─────────────────────────┘
                                         ▼
  FASE 6 ⭐      ┌─────────────────────────────────────────────────┐
  RETENTION &    │  lifecycle (valore anche a mercato fermo) +      │ → doc 07
  ESPANSIONE     │  upsell (EA→Difensivo→Bilanciato→Completo)+referral│
                 └─────────────────────────────────────────────────┘

  In parallelo a OGNI fase: RETARGETING.
```

## 2. Le fasi nel dettaglio (con le leve di Sabri)

### Fase 1 — Traffico (freddo → tiepido)
- **Canali**: Meta + YouTube primari; Google Search per la domanda consapevole; TikTok per volume.
- **Angolo Sabri**: l'annuncio NON vende. Offre **valore gratis** (Demo/Report/Quiz) ed
  **entra nella conversazione** già in testa al cliente (doc 02). CTA = "guardalo dal vivo".

### Fase 2 — Lead/Prova (la Demo è l'esca)
- **Demo read-only** (doc 04) = massima conversione (il prodotto vende sé stesso).
- **Value-in-advance**: dà prima di chiedere → debito di reciprocità (Cialdini/Sabri).
- **Open loop**: l'Ai risponde a 3 domande, poi la curiosità si chiude solo sbloccando.

### Fase 3 — Nurture (il "Magic Lantern")
- 5–7 email (doc 07): valore → storia → prove (storico/backtest) → obiezioni → offerta.
- **Slippery slide**: ogni email fa aprire la successiva (curiosità + bucket brigades).

### Fase 4 — Conversione (barriera bassa + rischio zero)
- **VSL + sales page** (doc 08) con la Godfather Offer (doc 03).
- Ingresso facile: **EA singolo 5€** o **Pacchetto Bilanciato 9€** (consigliato), **garanzia 30 giorni** ("meglio che gratis"). **Segnali + assistente AI inclusi in ogni EA/pacchetto.**
- **Upsell post-checkout** (Setup DFY) + spinta ai pacchetti (venduti sul **drawdown basso**).
- *Niente trial a tempo* (i trade D1 sono rari → mostrerebbe il vuoto, doc 16).

### Fase 5 — Attivazione ⭐ (dove si vince o si perde il business)
Iscriversi è facile; il rischio è **pagare e non installare** → niente valore → churn.
- **Onboarding immediato** (doc 07): "hai installato? serve aiuto?", guida "5 minuti" (doc 14).
- **DFY** come salvagente: "non vuoi farlo? lo facciamo noi" (setup a pagamento una tantum) → frizione → ricavo.
- **Trigger tecnico**: il server sa quando arriva il **primo dato** dell'EA del cliente →
  se non arriva entro X giorni, parte l'email/contatto di recupero.
- **KPI**: *tasso di attivazione* (iscritti → EA che invia dati). È qui il collo di bottiglia.

### Fase 6 — Retention & Espansione (il motore del LTV)
- **Valore anche a mercato fermo** (doc 16 §6): l'app/AI/notifiche danno motivi per
  tornare anche senza trade ("il sistema sta aspettando, è corretto").
- **Lifecycle email**: educazione, dietro le quinte, "il tuo mese in PHAI".
- **Upsell/ascensione**: singolo→Difensivo→Bilanciato→Completo, +DFY (doc 03 §8).
- **Referral**: "porta un amico, un mese gratis a entrambi" (loop virale, Sabri).

## 3. Pipeline operativa — cosa costruire, in ordine
1. **Dominio + HTTPS** (`app.phai.io`) — *prerequisito* (deploy/setup-domain.sh).
2. **Sito**: home + landing **Demo** + sales page + grazie + checkout.
3. **Demo read-only** collegata all'app (dati reali/di esempio, AI a domande limitate).
4. **CRM/email** con le 3 sequenze (nurture, onboarding/attivazione, retention) + tag.
5. **Checkout & licenze**: pagamento (PayPal/bonifico) → **license key** automatica → app
   (già fatto: `licensing.py`, `/api/pay/paypal/webhook`, `/api/admin/issue-license`).
6. **Tracciamento attivazione**: evento "primo dato EA ricevuto" per il recupero.
7. **Tracciamento**: pixel Meta, GA4, eventi (lead, checkout, **activation**, churn).
8. **Annunci** (doc 06) per i 3 sotto-avatar; **retargeting** su ogni fase.
9. **Dashboard KPI** (doc 09): MRR, attivazione, churn, LTV:CAC, payback.

## 4. Stack strumenti (lean)
| Funzione | Consigliato | Alternativa |
|---|---|---|
| Landing/sales page | Framer / Webflow / nel nostro stack | Carrd |
| Email/CRM + automazioni | Brevo / MailerLite | ActiveCampaign |
| Pagamenti + abbonamenti | **PayPal** (carte+PayPal) + bonifico manuale | Paddle (IVA gestita) |
| Licenze | nostro motore (`licensing.py`) | — |
| Demo | istanza read-only della nostra app | video screencast |
| Analytics | GA4 + Meta Pixel + eventi attivazione | Plausible |
| Hosting | VPS attuale (+ dominio/cert) | — |

## 5. Le 3 sequenze email (non più una sola)
A differenza del modello one-time, qui servono **tre** automazioni (doc 07):
1. **Nurture** (pre-vendita): lead → cliente.
2. **Onboarding/Attivazione** (post-acquisto): cliente → EA attivo.
3. **Retention/Lifecycle** (continuativa): cliente → cliente che resta e sale.

## 6. La regola d'oro (Sabri)
> **"Misura tutto."** Ma ora l'anello più debole spesso **non** è negli ads: è
> **l'attivazione** e il **churn**. Aggiusta quelli prima di versare benzina sul traffico.

---

### Collegato a
- Creatività → [06_COPY_ANNUNCI.md](06_COPY_ANNUNCI.md) · Email → [07_EMAIL_SEQUENCE.md](07_EMAIL_SEQUENCE.md)
- Numeri → [09_KPI_BUDGET_PIPELINE.md](09_KPI_BUDGET_PIPELINE.md) · Lente SaaS → [16_STRATEGIA_RIVISTA_SAAS.md](16_STRATEGIA_RIVISTA_SAAS.md)
- Onboarding cliente → [14_GUIDA_INSTALLAZIONE_CLIENTE.md](14_GUIDA_INSTALLAZIONE_CLIENTE.md)
