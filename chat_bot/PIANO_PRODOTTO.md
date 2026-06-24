# Piano prodotto — PAPP EA Chat (SaaS su singola VPS, feed condiviso)

> Stato: **piano approvato da redigere**, nessuna modifica al codice ancora applicata.
> Scenario confermato: **un EA gira sulla VPS**, tutti i compratori si loggano e
> guardano lo **stesso feed di segnali** + chattano. LLM gratuito (`opencode/deepseek`)
> con quota condivisa, gestito come risorsa scarsa.

## 0. Vincoli di progetto

- Tutto gira su **questa VPS** (16 vCPU, 31 GB RAM, ~189 GB liberi). Risorse abbondanti.
- **Un solo endpoint LLM gratuito**, rate limit condiviso da tutti gli utenti → collo di bottiglia unico.
- Feed segnali **condiviso** (no `user_id` sui segnali). Multi-tenant solo per: account + cronologia chat.
- Accesso **gratuito per chi ha comprato l'EA**, gated da license key.

## 1. Architettura target

```
Browser (login) ──HTTPS──> nginx/caddy (TLS) ──> FastAPI (uvicorn)
                                                   ├─ Auth (users + license_keys)
                                                   ├─ /ws            broadcast feed condiviso
                                                   ├─ /api/signals /api/stats   condivisi
                                                   ├─ /api/chat      → asyncio.Queue → LLM worker
                                                   └─ Postgres
EA (Wine) → papp_ea_log.jsonl → LogTailer → on_signal → DB + WS broadcast
LLM worker (1 task) ── token bucket ──> opencode/deepseek (quota condivisa)
        ▲ cache hit / riassunto condiviso = 0 chiamate LLM
```

Invariati: `LogTailer` (mt5_bridge.py), ossatura FastAPI/WS, modello `Signal`/`MarketSnapshot`.

---

## 2. Modifiche al database — `db.py`

### Nuovi modelli
- **`User`**: `id`, `email` (unique, index), `password_hash`, `license_key` (FK logica), `created_at`, `last_login`.
- **`LicenseKey`**: `id`, `key` (unique, index), `used_by_user_id` (nullable), `created_at`, `revoked` (bool default False).
- **`LlmCache`**: `id`, `cache_key` (unique, index, sha256 hex), `question`, `answer`, `hits` (int), `created_at`.
- **`DailySummary`**: `id`, `kind` (es. "perf_today"), `content`, `valid_until` (datetime), `created_at`.

### Modello modificato
- **`ChatHistory`**: aggiungere `user_id` (nullable durante migrazione, poi NOT NULL).

### Migrazione
`db.py` usa oggi `Base.metadata.create_all` → **crea solo tabelle nuove, non altera colonne esistenti**.
Opzioni:
- **(consigliata in fase dev)** Drop & recreate: i dati attuali sono di test. Aggiungere uno script `reset_db.py` che fa `drop_all` + `create_all`.
- (produzione futura) introdurre Alembic. Non ora.

---

## 3. Nuovo modulo — `llm_worker.py` (cuore del prodotto)

Responsabilità: isolare l'LLM dietro **una coda + un worker singolo**, con rate limit, cache e degradazione graceful.

### Strutture
- `queue: asyncio.Queue[Job]` dove `Job = {question, context, context_sig, future}`.
- `TokenBucket(rpm: int)`: limita le chiamate effettive a `LLM_RPM` (default 15, da `.env`).
- `worker()`: loop infinito che fa `await queue.get()`, applica rate limit, chiama `chat_logic.ask`, risolve il `future`. **Concorrenza verso l'LLM = 1.**

### Cache
- `cache_key = sha256(normalize(question) + "|" + context_sig)`.
  - `normalize`: lower, strip, collassa spazi.
  - `context_sig`: firma grossolana del contesto, es. `f"sig{last_signal_id}|{date.today()}"` → cache valida nella finestra giornaliera/per-nuovo-segnale.
- Lookup ordine: **LRU in memoria → tabella `LlmCache` → LLM**. Su hit DB incrementa `hits`. Su miss LLM, scrive in entrambe.
- LRU: `functools.lru_cache` non adatto (async + DB) → semplice `OrderedDict` con cap (es. 500).

### API pubblica del modulo
- `async def submit(question, context, context_sig) -> str`: cache-check → se miss accoda e attende il future. Applica anche **fairness per-utente** (vedi sotto, parametro `user_id`).
- `async def start_worker()` / `stop_worker()`: avviati/fermati nel `lifespan` di `app.py`.

### Fairness per-utente
- Dict `in_flight: dict[user_id, int]`. Se l'utente ha già 1 richiesta in volo → rifiuta con messaggio "attendi la risposta precedente".
- Rate limit leggero per utente (es. max 5/min) con un piccolo token bucket per `user_id`.

### Degradazione graceful
- Se `ask()` solleva timeout/errore o la quota è esaurita: ritorna ultima risposta cache pertinente, altrimenti stringa canned: *"Il servizio AI è momentaneamente al limite, riprova tra qualche minuto."* — **mai 500**.

---

## 4. Modifiche — `chat_logic.py`

- `ask()` resta concettualmente uguale (subprocess `opencode run`), ma:
  - viene chiamato **solo dal worker**, mai direttamente dagli endpoint.
  - aggiungere gestione errori esplicita (return `None` su fallimento, il worker decide il fallback).
  - timeout già presente (120s); renderlo configurabile `LLM_TIMEOUT`.
- Nessun cambio di provider. Se in futuro si passa a HTTP diretto, si tocca solo questa funzione.

---

## 5. Nuovo modulo — `auth.py`

- `hash_password` / `verify_password` con `passlib[bcrypt]` (nuova dipendenza).
- `create_session_token(user_id)` / `verify_token`: JWT con `python-jose` **oppure** cookie di sessione firmato (più semplice; preferito per MVP → `itsdangerous`).
- Dependency FastAPI `current_user(request)` che legge il cookie e ritorna lo `User` o solleva 401.
- `register(email, password, license_key)`:
  - valida che la `license_key` esista, non sia `revoked`, non sia già `used_by_user_id`.
  - crea `User`, marca la key come usata.
- `login(email, password)` → set cookie.
- Generazione license key: script `gen_license.py` (CLI) che inserisce N chiavi in `license_keys` e le stampa (da consegnare ai compratori).

---

## 6. Modifiche — `app.py`

### Lifespan
- Avviare `llm_worker.start_worker()` accanto al `LogTailer`.
- Avviare task periodico `refresh_daily_summary()` (ogni `SUMMARY_REFRESH_MIN`, default 30) che genera i riassunti condivisi una volta per tutti.

### Endpoint nuovi/modificati
- `POST /api/register` → `auth.register`.
- `POST /api/login` → `auth.login`, set cookie.
- `POST /api/logout`.
- `GET /` → se non loggato, servire `login.html`; se loggato, `index.html`. (oppure SPA che gestisce lo stato lato client).
- **Proteggere** `/api/chat`, `/ws`, `/api/signals`, `/api/stats`, `/api/market` con dependency `current_user`.
- `POST /api/chat`:
  - costruisce `context` e `context_sig` (come oggi + id ultimo segnale).
  - intercetta domande "comuni" → serve `DailySummary` senza LLM.
  - altrimenti `await llm_worker.submit(question, context, context_sig, user_id)`.
  - salva `ChatHistory` con `user_id`.

### Fix streaming SSE (bug attuale)
- Sostituire `yield f"data: {full}\n\n"` con un **singolo evento JSON**:
  `yield "data: " + json.dumps({"text": full}) + "\n\n"`.
- Client (`index.html`) parsa il JSON invece di concatenare righe grezze.
- Risolve il troncamento al primo paragrafo su risposte multi-riga.

---

## 7. Modifiche — `templates/` (frontend)

- **Nuovo `login.html`**: form email/password + campo license key per la registrazione.
- **`index.html`**:
  - parsing SSE come JSON (`JSON.parse(data).text`), opzionale effetto "typing" lato client.
  - mostrare stato coda ("in coda…", "il servizio è al limite…").
  - pulsante logout, mostrare email utente.
- Collegare (finalmente) il pannello mercato a `/api/market` se utile, oppure rimuoverlo dal codice morto.

---

## 8. Config — `.env` / `run.sh`

Nuove variabili:
```
SECRET_KEY=<random>            # firma cookie/JWT
LLM_RPM=15                     # token bucket globale verso l'LLM
LLM_TIMEOUT=120
LLM_USER_RPM=5                 # fairness per-utente
SUMMARY_REFRESH_MIN=30
CACHE_MAX=500
```
- **Rimuovere la password hardcoded** in `chat_logic.py` (default a riga 9): leggere solo da env, nessun default in chiaro nel codice.
- `.env` va in `.gitignore` (verificare che non sia già committato; se lo è, ruotare le credenziali).

---

## 9. Deployment / esposizione

- **Reverse proxy** caddy (TLS automatico Let's Encrypt) o nginx + certbot davanti a uvicorn `127.0.0.1:8000`.
- `uvicorn` dietro **systemd** (restart automatico) invece di `run.sh` manuale. Workers=1 (il worker LLM è singleton in-process → un solo processo uvicorn, oppure spostare il worker fuori processo se in futuro si scala; per ora **1 worker uvicorn**).
- Dominio + record DNS.
- Backup periodico di Postgres (cron `pg_dump`).

---

## 10. Ordine di costruzione (fasi con criteri di accettazione)

| Fase | Contenuto | Rischio | Criterio "fatto" |
|------|-----------|---------|------------------|
| **1** | Fix streaming SSE (JSON event) + parsing client | Basso | Risposta multi-paragrafo appare intera in UI |
| **2** | `llm_worker.py`: coda + worker + token bucket + cache; `app.py`/`chat_logic.py` instradati | Medio | 20 domande concorrenti → 1 sola chiamata LLM per domanda unica, ripetute servite da cache |
| **3** | `auth.py` + `users`/`license_keys` + endpoint login/register + protezione endpoint + `login.html` | Medio | Solo con license key valida si crea account; senza login → 401 |
| **4** | Riassunti condivisi + degradazione graceful + fairness per-utente | Basso | Domande comuni = 0 chiamate LLM; quota esaurita = messaggio gentile, no 500 |
| **5** | TLS (caddy) + systemd + backup pg_dump | Basso | App raggiungibile su https://dominio, riavvio automatico |

Ogni fase è indipendente e rilasciabile: dopo la 1 hai già un miglioramento visibile; dopo la 3 hai un prodotto multi-utente reale.

---

## 11. Rischi e mitigazioni

- **Free tier LLM più stretto del previsto** → `LLM_RPM` basso strozza tutti. Mitigazione: cache + riassunti condivisi assorbono la maggior parte; valutare upgrade a tier a pagamento se gli utenti crescono.
- **`opencode run` instabile sotto carico** (attach alla desktop app) → unica via attraverso il worker riduce la concorrenza a 1, ma resta un single point of failure. Mitigazione futura: HTTP diretto al provider.
- **License key condivise tra compratori** (pirateria) → key monouso (`used_by_user_id`), eventualmente binding a 1 sola sessione attiva.
- **Dati finanziari + linguaggio "consulenza"** → aggiungere disclaimer legale ben visibile ("non è consulenza finanziaria").
- **`create_all` non migra colonne** → in dev drop&recreate; in prod Alembic prima del primo cliente reale.

---

## 12. Nuove dipendenze (`requirements.txt`)

```
passlib[bcrypt]>=1.7      # hashing password
itsdangerous>=2.0         # firma cookie sessione (o python-jose per JWT)
```
(Tutto il resto è già presente: fastapi, uvicorn, sqlalchemy, asyncpg.)
