# Email drip automatico (con Brevo)

La campagna email parte **da sola**, pilotata dal nostro stack, con **Brevo** come motore
di consegna (ottima inbox placement). Codice: [`chat_bot/email_drip.py`](../chat_bot/email_drip.py)
+ contenuti in `chat_bot/email_campaign.json` (sorgente: `pipeline/email_campaign.py`).

## Cosa automatizza ORA
- **NURTURE (8 email)**: parte quando un lead lascia l'email (`leads.created_at`), una email
  per giorno secondo il piano. Si **ferma** se il lead diventa cliente.
- **CODA (2 email)**: re-engagement solo a chi NON ha ancora acquistato.
- Ogni email inviata **una volta sola** (tabella `email_sent`), con **disiscrizione** e
  disclaimer di rischio nel footer.

> Onboarding e retention dipendono da **eventi dell'app** (acquisto, primo dato, mese piatto):
> si agganciano in un secondo momento (vedi "Fase 2").

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
Le email contengono `{{unsubscribe}}` → `…/unsub?e=<email>`. Va aggiunta una rotta
`GET /unsub` che setta `leads.unsubscribed=true` (1 endpoint, da fare prima del live).
In alternativa, usando Brevo come **marketing email**, la disiscrizione è gestita da Brevo.

## Fase 2 (quando vuoi): onboarding + retention
Agganciare gli eventi dell'app al drip:
- **acquisto** (`licensing.issue_license`) → avvia onboarding;
- **primo dato EA** (`process_event` primo segnale utente) → "Sei LIVE";
- **mese piatto / disdetta** → email dedicate.
Si fa chiamando `email_drip` (o l'API Brevo) da quei punti. Te lo costruisco quando arriviamo lì.
