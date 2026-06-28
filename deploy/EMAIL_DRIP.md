# Email drip automatico (con Brevo)

La campagna email parte **da sola**, pilotata dal nostro stack, con **Brevo** come motore
di consegna (ottima inbox placement). Codice: [`chat_bot/email_drip.py`](../chat_bot/email_drip.py)
+ contenuti in `chat_bot/email_campaign.json` (sorgente: `pipeline/email_campaign.py`).

## Cosa automatizza ORA (tutte e 3 le sequenze)
Tutto è **derivato dallo stato del DB** — nessun hook nel resto dell'app.
- **NURTURE (8)**: da `leads.created_at`, una al giorno; si ferma se il lead diventa cliente.
- **CODA (2)**: re-engagement solo a chi NON ha acquistato.
- **ONBOARDING (1–6)**: per ogni cliente (User+licenza valida). 'primo dato' = primo
  Signal/AccountSnapshot del cliente; 'nessun dato 24h' = niente dati dopo l'acquisto.
- **RETENTION**: settimanale + recap mensile (dedup per periodo), **mese-piatto** (0 trade
  in 30g), **upsell** (Starter→Pro a +7g, Pro→Annuale a +90g, Elite per heavy-user AI),
  **referral** (+30g), **win-back** (licenza scaduta).
- **Disiscrizione**: rotta `GET /unsub?e=<email>` (già attiva) → vale anche per i clienti.
- Ogni email **una volta sola** (`email_sent`); le ricorrenti ripartono ogni periodo.
- Anti-raffica: le email a tempo arretrate >36h vengono saltate (niente blast al primo avvio).

> Nota: `retention-win` (email a ogni trade in profitto) è l'unica NON automatizzata via cron
> (troppo per-evento/rumorosa); si aggancia se serve da `process_event`.

## Attivazione (3 passi)
1. **Crea un account Brevo** (free: 300 email/giorno) → Impostazioni → SMTP & API →
   **crea una API key**.
2. Aggiungi al `.env`:
   ```ini
   BREVO_API_KEY=xkeysib-...........
   SMTP_FROM=PHAI Trading <no-reply@tuodominio.com>   # mittente verificato in Brevo
   APP_PUBLIC_URL=https://app.tuodominio.com          # per i link nelle email
   ```
   (Senza `BREVO_API_KEY` ma con `SMTP_*` usa SMTP; senza nulla resta in **dry-run** = logga soltanto.)
3. **Pianifica il tick** (ogni ora) con cron:
   ```bash
   ( crontab -l 2>/dev/null; echo '7 * * * * cd /home/pietro_giacobazzi/Desktop/PAPP_EA/chat_bot && set -a && . ./.env && set +a && /usr/bin/python3 email_drip.py tick >> /tmp/phai-drip.log 2>&1' ) | crontab -
   ```

## Comandi utili
```bash
cd chat_bot && set -a && . ./.env && set +a
python3 email_drip.py status        # lead, email inviate, provider
python3 email_drip.py tick --dry    # cosa invierebbe ADESSO, senza inviare
python3 email_drip.py tick          # invia le email dovute
```

## Sicurezza anti-raffica
Al primo avvio NON spara tutte le email arretrate: salta quelle in ritardo oltre
`DRIP_SKIP_OLDER_HOURS` (default 36h). I lead nuovi ricevono la sequenza dal giorno 0 in poi.

## Disiscrizione
Le email contengono `{{unsubscribe}}` → `…/unsub?e=<email>`. La rotta `GET /unsub` **è già
attiva**: segna l'indirizzo come `unsubscribed` (crea il record lead se non esiste, così la
soppressione vale anche per i clienti). Il drip salta sempre gli indirizzi disiscritti.
