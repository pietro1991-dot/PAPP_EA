# 12 · Delivery & Onboarding — come PHAI gira sui conti dei clienti

> Il modello di business (doc 11) è scelto. Questo documento risponde alla domanda
> operativa più importante: **come faccio, in pratica, a far girare PHAI sul conto
> di un cliente che paga — e a fargli vedere il SUO conto nella SUA dashboard?**

---

## 1. La domanda ha DUE metà (non confonderle)
1. **Esecuzione** — l'EA deve aprire/chiudere ordini **sul conto del cliente**.
2. **Telemetria** — i dati di quel conto (segnali, saldo, performance) devono
   arrivare alla **dashboard + assistente AI** del cliente.

Sono due problemi distinti. Il primo è "trading"; il secondo è "SaaS". PHAI li ha
entrambi e vanno risolti entrambi.

> ⚠️ **Principio guida (regolatorio):** il cliente tiene SEMPRE il controllo dei
> propri soldi sul PROPRIO conto broker. Tu vendi **software**, non gestisci denaro
> altrui. Questo ti tiene fuori dalla gestione del risparmio / consulenza
> regolamentata (→ [doc 10](10_COMPLIANCE_DISCLAIMER.md)). Non chiedere mai accesso
> ai fondi; al massimo (e solo come servizio tecnico) installi il software per loro.

---

## 2. I tre modelli di delivery (e quale scegliere)

### Modello 1 — EA distribuito (self-hosted dal cliente) ✅ CONSIGLIATO
Il cliente installa l'EA sul **proprio** MetaTrader 5 (sul suo PC o, meglio, su una
sua VPS). L'EA, all'avvio, **valida la licenza** col tuo server e, se ok, **opera
sul conto del cliente** e **invia la telemetria** alla tua piattaforma.
- ✅ **Scala all'infinito** (ogni cliente è autonomo), costo marginale ~0.
- ✅ Tu **non tocchi mai i fondi** → rischio regolatorio minimo.
- ✅ Si integra con il SaaS (licenza + dashboard) già impostato.
- ❌ Richiede un'installazione (attrito) → mitigato da guida + upsell "Fatto-Per-Te".
- ❌ Richiede sviluppo: **licenza nell'EA + invio dati remoto** (vedi §4).

### Modello 2 — Copy-trading da un master
Tu fai girare un **conto master**; i conti dei clienti **copiano** le operazioni
(copier EA o sistema di copy del broker).
- ✅ Zero installazione della logica per il cliente.
- ❌ Dipendi da un broker/copier; slippage e differenze tra conti; e "fornire
  operazioni da copiare" può scivolare verso la **consulenza/segnali regolamentati**.
- ❌ Non valorizza la dashboard per-conto (tutti copiano lo stesso master).
- Verdetto: alternativa, non la via principale.

### Modello 3 — VPS gestita "Fatto-Per-Te" (DFY)
Tu prepari una VPS, installi MT5 loggato sul conto del cliente, installi l'EA.
- ✅ Attrito ZERO per il cliente (non tocca niente).
- ❌ Maneggi le **credenziali broker** del cliente (sicurezza, fiducia, responsabilità).
- ❌ **Manuale** → non scala (ore-uomo per cliente).
- Verdetto: ottimo come **servizio opzionale a pagamento una tantum** (setup DFY, doc 03/11), NON come modello base.

> **Scelta:** Modello 1 (distribuito) come standard, con il Modello 3 (DFY) come
> upsell per i non-tecnici. È esattamente la value ladder del doc 11.

---

## 3. Lo stato attuale (cosa c'è e cosa manca — onesto)
**C'è già:**
- App SaaS con **login**, **utenti**, **license key** (modelli `User`/`LicenseKey`).
- Pipeline dati: l'EA scrive un **log JSONL locale** → `mt5_bridge.py` lo legge →
  Postgres → dashboard. Funziona **solo per un conto sulla/vicino alla TUA VPS**.

**Manca (da costruire) per servire clienti esterni:**
1. **Controllo licenza dentro l'EA** (oggi l'EA non sa nulla di licenze: nessun
   `WebRequest`, nessun check). Senza, chiunque abbia il file `.ex5` lo userebbe gratis.
2. **Telemetria remota multi-tenant**: l'EA del cliente deve **mandare i dati al tuo
   server via HTTP**, etichettati per utente. Oggi scrive solo un file locale che
   solo la tua VPS legge.
3. **Enforcement dell'abbonamento**: se il cliente disdice, la licenza deve
   diventare inattiva e l'EA **smettere di operare**.

Questi tre pezzi sono il lavoro che trasforma "il mio EA sul mio conto" in
"prodotto vendibile sui conti di mille clienti".

---

## 4. L'architettura target (cosa costruire)

```
 CLIENTE (suo PC / sua VPS)                      TUO SERVER (VPS)
 ┌───────────────────────────┐                  ┌──────────────────────────────┐
 │  MetaTrader 5              │                  │  API PHAI (FastAPI)          │
 │   └ EA PHAI + indicatore   │   1. licenza     │   • POST /api/ea/validate    │
 │     • all'avvio valida     │ ───WebRequest──► │     (key+account → ok/deny)  │
 │       la licenza           │                  │   • POST /api/ea/ingest      │
 │     • opera sul conto      │   2. telemetria  │     (key+segnali+conto)      │
 │       del cliente          │ ───WebRequest──► │        │                     │
 │     • invia i dati         │                  │        ▼                     │
 └───────────────────────────┘                  │   Postgres (multi-tenant:    │
                                                 │   ogni dato legato a user_id)│
 ┌───────────────────────────┐                  │        │                     │
 │  Cliente apre l'app/PWA    │ ◄────────────────┤   Dashboard + AI mostrano    │
 │  vede il SUO conto + AI    │   3. visualizza  │   SOLO i dati di quel utente │
 └───────────────────────────┘                  └──────────────────────────────┘
```

### 4.1 Licenza nell'EA (anti-pirateria + enforcement abbonamento)
- All'avvio (`OnInit`) e poi periodicamente (es. ogni 6–24h), l'EA fa una
  `WebRequest` a `POST /api/ea/validate` con: **license key**, **numero di conto**,
  **broker**.
- Il server risponde:
  - `ok`: licenza attiva, abbonamento valido, key non già legata ad altro conto.
  - `deny`: scaduta/disdetta/chiave usata altrove → l'EA **non apre nuove
    operazioni** (e mostra un messaggio).
- **Binding key↔conto**: alla prima validazione la key si "lega" al numero di conto
  → evita che una sola licenza giri su 100 conti.

### 4.2 Telemetria remota (il SaaS multi-tenant)
- L'EA invia gli eventi (apertura/chiusura/skip + snapshot conto + market) a
  `POST /api/ea/ingest` con la **license key** come autenticazione.
- Il server ricava `user_id` dalla key e salva **i dati associati a quell'utente**
  (i modelli `Signal`/`AccountSnapshot` prendono una colonna `user_id`).
- La dashboard e l'AI filtrano per utente loggato → ognuno vede **solo il proprio
  conto**.
- **Due strade per l'invio:**
  - **(a) WebRequest diretta dall'EA** (più semplice da distribuire, niente
    software extra sul PC del cliente). Richiede che il cliente **whitelist-i il tuo
    dominio** in MT5 (vedi §5, è un passaggio di setup obbligatorio).
  - **(b) Piccolo "uploader" locale** (l'EA scrive il log, un mini-agente lo invia):
    più robusto offline, ma è un secondo software da installare. Per iniziare,
    **scegli (a)**.

### 4.3 Vincolo MetaTrader: la whitelist WebRequest
MT5 permette le `WebRequest` **solo verso URL autorizzati** in
*Strumenti → Opzioni → Expert Advisors → "Consenti WebRequest per i seguenti URL"*.
→ L'onboarding DEVE includere "aggiungi `https://app.tuodominio.com` a questa lista".
È un passaggio noto di tutti gli EA che comunicano via web; lo mettiamo nella guida
con screenshot. (Con il dominio + HTTPS che stai per prendere, questo diventa pulito.)

---

## 5. Il flusso di onboarding del cliente (passo-passo)
Dal pagamento all'operatività:

1. **Acquisto** → checkout (Stripe/Paddle) → si genera una **license key** monouso
   e si crea l'account app.
2. **Email di benvenuto** con: credenziali app, license key, link alla guida.
3. **Il cliente sceglie dove far girare l'EA:**
   - *Da solo*: sul suo PC (deve restare acceso) o, consigliato, su una **VPS Forex**
     (sempre accesa, ~5–15 €/mese da provider tipo ForexVPS/Contabo).
   - *Fatto-Per-Te*: paga l'upsell e lo configuri tu.
4. **Installazione** (guida con screenshot):
   - Copia `PHAI_Median.ex5` (indicatore) e `EA_PHAI.ex5` nelle cartelle MT5.
   - Aggiungi il dominio PHAI alla whitelist WebRequest.
   - Trascina l'EA sul grafico (EURUSD/GBPUSD/USDCHF), incolla la **license key**
     negli input, abilita "Trading algoritmico".
5. **Attivazione**: l'EA valida la licenza → inizia a operare e a inviare dati.
6. **Verifica**: il cliente apre l'app/PWA → vede il **suo** conto, i segnali, l'AI.
7. **Supporto/retention** (doc 07): check "hai installato?", primo risultato, ecc.

## 6. Scelte broker (e l'aggancio IB del doc 11)
- L'EA gira su **qualunque broker MT5** con EURUSD/GBPUSD/USDCHF e trading
  algoritmico permesso. Documenta **impostazioni consigliate** (tipo conto, spread
  bassi, leva, fuso del server).
- Qui si innesta l'**IB rebate** (doc 11 §6): consigli un broker partner (link IB),
  in modo **trasparente**. Bonus: con un broker noto controlli meglio spread/condizioni
  e riduci i ticket di supporto.

## 7. Sicurezza e fiducia (non negoziabili)
- **Mai** chiedere la password di trading/prelievo del cliente. Per il DFY serve solo
  la **login MT5** (trading), e va trattata con cura (password manager, niente invii
  in chiaro, possibilità di revoca).
- License key **legata al conto** e **revocabile** dal tuo pannello (disdetta → stop).
- Comunicazione onesta: l'EA opera secondo i pattern, ma **il rischio resta del
  cliente** (drawdown possibili) → aspettative corrette = meno rimborsi (doc 10).

---

## 8. Il lavoro tecnico minimo per partire (MVP)
In ordine di priorità (questo è ciò che sblocca le vendite a clienti veri):
1. **Endpoint `POST /api/ea/ingest`** (telemetria) + colonna `user_id` su
   `Signal`/`AccountSnapshot` (multi-tenant). *Sblocca la dashboard per-cliente.*
2. **Endpoint `POST /api/ea/validate`** (licenza) + binding key↔conto + stato
   abbonamento. *Sblocca anti-pirateria + enforcement.*
3. **Modifiche all'EA**: input `LicenseKey`, `WebRequest` di validate + ingest,
   stop se `deny`. *Rende l'EA un prodotto.*
4. **Guida di installazione** con screenshot (incl. whitelist WebRequest).
5. **Checkout → generazione license key** automatica (Stripe/Paddle webhook).
6. *(poi)* Pannello admin per vedere/revocare licenze e conti attivi.

> Stima: è un blocco di lavoro circoscritto e fattibile sul codice esistente (l'app
> ha già utenti/licenze; l'EA ha già il logging strutturato da convertire in invio
> HTTP). Una volta fatto, l'onboarding di un nuovo cliente è **completamente
> self-service** e scalabile.

---

### Collegato a
- Il modello e i prezzi → [11_MODELLO_BUSINESS.md](11_MODELLO_BUSINESS.md)
- L'upsell DFY e i piani → [03_GODFATHER_OFFER.md](03_GODFATHER_OFFER.md)
- Regole su fondi/consulenza → [10_COMPLIANCE_DISCLAIMER.md](10_COMPLIANCE_DISCLAIMER.md)
