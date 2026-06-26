# 🔗 Chatbot PAPP EA — link pubblico e controllo

## Link da condividere (funziona anche fuori dalla VPS)

La VPS ora è **dedicata a PAPP**: l'IP nudo apre direttamente il chatbot, senza porta.

| | URL |
|---|---|
| **Consigliato (no avviso)** | **http://77.81.226.151** |
| HTTPS (cifrato) | https://77.81.226.151 |
| Legacy | https://77.81.226.151:8095 · http://77.81.226.151:8090 |

> ⚠️ Su **HTTPS** il certificato è **self-signed** → avviso del browser ("Avanzate → Procedi").
> Su **HTTP** (porta 80) nessun avviso, ma il traffico non è cifrato (il login passa in chiaro).
> Per un HTTPS pulito serve un dominio + Let's Encrypt (vedi in fondo).

Chi apre il link vede la dashboard e può **registrarsi con una license key** (una per utente,
generata con `chat_bot/gen_license.py`) e poi fare domande all'assistente, che conosce
il backtest ufficiale EURUSD (config, drawdown, profit factor, ecc.).

## Avviare / fermare a piacimento

Dallo script nella root del progetto:

```bash
./chatbot-ctl.sh start      # accende il chatbot → il link funziona
./chatbot-ctl.sh stop       # spegne il chatbot → il link dà errore 502
./chatbot-ctl.sh restart    # riavvia
./chatbot-ctl.sh status     # stato servizi, porte e link
```

Cosa gestisce: `papp-chat.service` (l'app web) + `opencode-serve.service` (il motore LLM).
`nginx` (il proxy pubblico) resta sempre attivo perché è condiviso.
> I servizi sono di sistema: se richiesto, lo script chiede la password con `sudo`.

## Perché il link è raggiungibile da fuori

- L'app è in ascolto su `0.0.0.0:8090` e nginx su `0.0.0.0:8095` (non solo localhost).
- ✅ **Firewall locale (host): verificato aperto** su 8095 e 8090 (test di connessione
  attraverso la catena INPUT → HTTP 200). Non è l'host a bloccare.
- Restano due condizioni fuori dall'host:
  1. il **firewall del provider** (pannello cloud / security group) deve permettere **8095**
     (e/o 8090) in ingresso — questo non è testabile dall'interno della VPS;
  2. l'IP pubblico `77.81.226.151` deve restare quello (se cambia, aggiorna questo file e
     `chatbot-ctl.sh`).

## Altri progetti (fermati il 2026-06-26)

Per dedicare la VPS a PAPP sono stati **fermati e disabilitati** questi servizi e i loro
siti nginx: `pm2-pietro_giacobazzi` (ai-act), `packi-v2`, `paki-workspace` (MO.VE), `trading-dashboard`.
Backup nginx in `/etc/nginx/sites-enabled.bak.20260626_155230/` e `papp-chat.conf.bak.20260626_155230`.

Per **ripristinarli tutti** (e riportare PAPP su :8095 com'era):
```bash
./ripristina-altri-progetti.sh        # nella root del progetto, chiede sudo
```

## Opzionale: link "pulito" senza avviso del browser

Serve un **dominio** puntato a `77.81.226.151` + certificato Let's Encrypt. In breve:
1. registra un dominio (es. `papp.tuonome.com`) e fai puntare un record A all'IP;
2. usa `chat_bot/deploy/nginx-papp.conf` (porta 443) al posto del self-signed;
3. `sudo certbot --nginx -d papp.tuonome.com`.
Poi il link diventa `https://papp.tuonome.com` senza avvisi.
