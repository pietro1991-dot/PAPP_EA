# Pagamenti → licenze (PayPal · carte · bonifici)

Motore agnostico ([`chat_bot/licensing.py`](../chat_bot/licensing.py)): un solo punto
emette le license key, da qualsiasi sorgente. Endpoint in `app.py`.

| Metodo | Come arriva la key |
|---|---|
| **PayPal + carte** | webhook automatico `/api/pay/paypal/webhook` → key emessa e inviata via email |
| **Bonifico / vendita diretta** | endpoint admin `/api/admin/issue-license` → emetti con un comando |
| **Stripe/Paddle (futuro)** | basta un nuovo webhook che chiama `licensing.issue_license()` |

> Idempotente per `external_id`: i webhook rispediti non creano doppioni.
> Disdetta abbonamento PayPal → `active=False` → l'EA smette di aprire (enforcement).

---

## 1. Variabili d'ambiente (`.env`)
```ini
# Emissione manuale (bonifici/vendite dirette)
ADMIN_TOKEN=<gia-impostato, vedi .env>

# Email di consegna key (se assente: la key viene solo loggata)
SMTP_HOST=smtp.tuoprovider.com
SMTP_PORT=587
SMTP_USER=no-reply@tuodominio.com
SMTP_PASS=********
SMTP_FROM=PHAI Trading <no-reply@tuodominio.com>
APP_PUBLIC_URL=https://app.tuodominio.com

# PayPal (lascia vuoto finché non configuri: il webhook risponde 503)
PAYPAL_CLIENT_ID=...
PAYPAL_SECRET=...
PAYPAL_WEBHOOK_ID=...
PAYPAL_API=https://api-m.paypal.com           # sandbox: https://api-m.sandbox.paypal.com
PAYPAL_PLAN_MAP={"P-XXXXXXXX":"pro","P-YYYY":"starter"}   # (webhook) plan_id PayPal -> nostro piano

# Checkout sul sito (pulsanti PayPal): i plan_id degli abbonamenti + prezzo lifetime
PAYPAL_PLAN_STARTER=P-XXXXXXXXXXXXX     # plan_id del piano Starter 49€/mese
PAYPAL_PLAN_PRO=P-YYYYYYYYYYYYY         # plan_id del piano Pro 97€/mese
PAYPAL_LIFETIME_PRICE=997               # prezzo pagamento unico Lifetime
PAYPAL_CURRENCY=EUR
```

## Il checkout sul sito (pulsanti PayPal)
- Pagina **`/checkout?plan=starter|pro|lifetime`** (i pulsanti dei piani sulla landing
  ci puntano). Mostra i **pulsanti PayPal** (abbonamento per Starter/Pro, pagamento
  unico per Lifetime) caricati con `PAYPAL_CLIENT_ID`.
- Flusso: il cliente inserisce l'email → paga su PayPal → `POST /api/pay/paypal/confirm`
  **verifica il pagamento lato server** (con `PAYPAL_SECRET`) → emette la key e la mostra
  + la invia via email → bottone "Registra ora" con la key **già precompilata**.
- Il **webhook** (`/api/pay/paypal/webhook`) resta il backstop affidabile (idempotente).
- Finché `PAYPAL_CLIENT_ID`/`SECRET` sono vuoti, il checkout mostra un **fallback
  elegante** ("contattaci / bonifico") — nessun pulsante morto.

## 2. Emettere una key a mano (bonifico) — un comando
Quando ricevi un bonifico, emetti la key (parte l'email automatica se SMTP è configurato):
```bash
curl -s -X POST https://app.tuodominio.com/api/admin/issue-license \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"email":"cliente@email.com","plan":"pro"}'
# -> {"ok":true,"key":"XXXXX-XXXXX-XXXXX-XXXXX","reused":false}
```
Opzioni: `"plan"` = starter|pro|elite; `"months": 12` per scadenza (lifetime = ometti);
`"external_id"` per idempotenza (riemettere non duplica).

## 3. PayPal — setup (una volta)
1. Vai su **developer.paypal.com → Apps & Credentials**, crea un'app → ottieni
   **Client ID** e **Secret** (mettili in `.env`).
2. (Abbonamenti) crea i **Subscription Plans** (Starter/Pro) → annota i `plan_id`,
   mettili in `PAYPAL_PLAN_MAP`.
3. **Webhooks**: aggiungi l'URL
   `https://app.tuodominio.com/api/pay/paypal/webhook` e iscrivilo agli eventi:
   - `BILLING.SUBSCRIPTION.ACTIVATED` (emette la key)
   - `BILLING.SUBSCRIPTION.CANCELLED`, `.SUSPENDED`, `.EXPIRED` (disattiva)
   - `PAYMENT.SALE.COMPLETED` / `PAYMENT.CAPTURE.COMPLETED` (one-time / lifetime)
   Copia il **Webhook ID** in `PAYPAL_WEBHOOK_ID`.
4. Nel bottone/checkout PayPal, imposta `custom_id` con l'email del compratore se
   usi pagamenti one-time (per le subscription PayPal fornisce già l'email).
5. Riavvia il servizio. Testa con un pagamento in **sandbox** prima del live.

> Sicurezza: il webhook **verifica la firma** PayPal (verify-webhook-signature).
> Senza credenziali valide risponde 503/400 e NON emette nulla.

## 4. Il flusso completo per il cliente
Paga (PayPal/carta) **o** bonifico → riceve **email con la key** → si registra
sull'app con quella key → installa l'EA → opera. Disdice → licenza disattivata.

## 5. IVA/Tasse (importante)
PayPal/Stripe **non gestiscono l'IVA** sui prodotti digitali: te ne occupi tu
(regime OSS UE). Se vuoi che la gestisca un terzo (merchant of record), usa
**Paddle**: stesso motore licenze, basta aggiungere un webhook che chiama
`licensing.issue_license()`. Vedi [marketing/10](../marketing/10_COMPLIANCE_DISCLAIMER.md).
