# deploy/ — attivazione dominio + HTTPS (pronta all'uso)

Tutto pronto per dare a PHAI un **dominio con HTTPS valido** (Let's Encrypt) appena
lo compri. Serve perché:
- MetaTrader **rifiuta i certificati self-signed** nelle WebRequest → senza dominio
  valido la **licenza/telemetria degli EA dei clienti NON funziona**;
- sblocca **PWA installabile + notifiche push** affidabili su mobile;
- niente più avviso "sito non sicuro" nel browser.

## File
- **`setup-domain.sh`** — script automatico: nginx + Let's Encrypt + rinnovo, in un comando.
- **`nginx-phai.conf`** — il server block finale di riferimento (lo genera lo script; qui per revisione).

---

## Attivazione in 5 minuti (quando hai il dominio)

### Passo 0 — Compra il dominio e punta il DNS
1. Compra un dominio (es. `phai.io`) da un registrar (Namecheap, Cloudflare, ecc.).
2. Crea un record **A**: `app.tuodominio.com` → **77.81.226.151**.
3. Aspetta la propagazione (di solito pochi minuti). Verifica sulla VPS:
   ```
   dig +short app.tuodominio.com      # deve restituire 77.81.226.151
   ```

### Passo 1 — Lancia lo script (un comando)
Sulla VPS, nella cartella del progetto:
```
sudo bash deploy/setup-domain.sh app.tuodominio.com tua@email.com
```
Lo script:
1. crea il server block nginx per il dominio (instrada per `server_name`, **non
   tocca gli altri 4 siti** della VPS);
2. ottiene il certificato Let's Encrypt (metodo **webroot**, nessun downtime);
3. riscrive la config con **HTTPS + redirect 80→443**;
4. imposta il **rinnovo automatico** (cron giornaliero + reload nginx).

### Passo 2 — Verifica
```
curl -I https://app.tuodominio.com      # atteso: HTTP/2 200
```
Apri `https://app.tuodominio.com` nel browser: **lucchetto verde**, niente avvisi.

### Passo 3 — Aggiorna gli EA (una volta)
- Imposta negli EA `InpServerUrl = https://app.tuodominio.com` (default) e ricompila,
  **oppure** consegna ai clienti il preset `.set` con l'URL già dentro.
- Nella guida cliente (`marketing/14`) l'indirizzo da autorizzare in
  *Strumenti > Opzioni > EA > WebRequest* è proprio `https://app.tuodominio.com`.

Fatto: da qui l'onboarding dei clienti funziona end-to-end (licenza, telemetria,
PWA, notifiche).

---

## Note tecniche
- La VPS condivide nginx con altri 4 siti (ai-act, move, packi-v2, trading-dashboard).
  Lo script aggiunge **solo** `sites-available/phai.conf` + symlink in `sites-enabled/`
  e instrada per `server_name`: **non modifica** `papp-chat.conf` né gli altri.
- `papp-chat.conf` (porta 8095 self-signed) resta come fallback/accesso diretto.
- L'app continua a girare su `127.0.0.1:8090`; nginx fa solo da reverse proxy TLS.
- Rinnovo: `certbot renew` via cron alle 03:17, con `--deploy-hook "systemctl reload nginx"`.
- Per più nomi (es. anche `tuodominio.com` e `www`): aggiungi `-d` nello script o
  rilancia `certbot` con i nomi extra e aggiorna i `server_name`.

## Rollback
```
sudo rm /etc/nginx/sites-enabled/phai.conf
sudo nginx -t && sudo systemctl reload nginx
```
(Il certificato resta in `/etc/letsencrypt/` per riusi futuri.)
