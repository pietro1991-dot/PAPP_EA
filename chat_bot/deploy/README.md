# Deploy — PAPP EA Chat (produzione su VPS)

Architettura: **nginx (TLS) → uvicorn 127.0.0.1:8000 → Postgres**, con servizio
gestito da systemd e backup giornaliero del DB.

I comandi seguenti vanno eseguiti **come root** (`sudo`). IP VPS: `77.81.226.151`.

---

## 1. Servizio applicativo (systemd)

```bash
sudo cp deploy/papp-chat.service /etc/systemd/system/papp-chat.service
sudo systemctl daemon-reload
sudo systemctl enable --now papp-chat
sudo systemctl status papp-chat        # verifica che sia "active (running)"
journalctl -u papp-chat -f             # log in tempo reale
```

L'app ora gira su `127.0.0.1:8000`, si riavvia da sola al crash e al reboot, e
carica le variabili da `.env` (`COOKIE_SECURE=1` è forzato dal service, dietro TLS).

> Prerequisito: i pacchetti Python sono installati per l'utente `pietro_giacobazzi`
> (`pip install --user -r requirements.txt`). `/usr/bin/python3` legge `~/.local`.

---

## 2. Reverse proxy + TLS (nginx)

### Opzione A — con dominio (consigliata, certificato valido)

1. Punta un record DNS A del tuo dominio (es. `papp.tuodominio.it`) → `77.81.226.151`.
2. Modifica `deploy/nginx-papp.conf` sostituendo `papp.example.com` col dominio.
3. Installa la config e i certificati:

```bash
sudo cp deploy/nginx-papp.conf /etc/nginx/sites-available/papp
sudo ln -sf /etc/nginx/sites-available/papp /etc/nginx/sites-enabled/papp
sudo nginx -t && sudo systemctl reload nginx

# Certificato Let's Encrypt automatico (aggiunge anche il blocco HTTPS + redirect)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d papp.tuodominio.it
```

Dopo certbot, l'app è raggiungibile su `https://papp.tuodominio.it` con TLS valido
e rinnovo automatico.

### Opzione B — senza dominio (solo IP, certificato self-signed)

Browser mostrerà un avviso di sicurezza: accettabile per test, **non** per vendita.

```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/papp.key -out /etc/nginx/ssl/papp.crt \
  -subj "/CN=77.81.226.151"
```

Poi nel blocco HTTPS di `nginx-papp.conf` usa:
```
ssl_certificate     /etc/nginx/ssl/papp.crt;
ssl_certificate_key /etc/nginx/ssl/papp.key;
```

---

## 3. Backup giornaliero del DB (systemd timer)

```bash
sudo cp deploy/papp-backup.service /etc/systemd/system/papp-backup.service
sudo cp deploy/papp-backup.timer   /etc/systemd/system/papp-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now papp-backup.timer
systemctl list-timers papp-backup.timer      # prossima esecuzione
```

I dump vanno in `~/papp_backups/` (rotazione: 14 copie, configurabile via
`BACKUP_DIR` / `BACKUP_RETENTION` nel `.env`). Test manuale:

```bash
./deploy/backup_db.sh
```

> Alternativa cron (se preferisci): `30 3 * * * /home/pietro_giacobazzi/Desktop/PAPP_EA/chat_bot/deploy/backup_db.sh`

---

## 4. Generare le license key da vendere

```bash
cd /home/pietro_giacobazzi/Desktop/PAPP_EA/chat_bot
set -a && . ./.env && set +a
python3 gen_license.py 10      # stampa 10 chiavi da consegnare agli acquirenti
```

---

## 5. Checklist pre-vendita

- [ ] `papp-chat` attivo e con restart automatico
- [ ] HTTPS valido (Opzione A) — **non** self-signed per clienti reali
- [ ] `SECRET_KEY` robusta in `.env` (già generata); `.env` non nel git
- [ ] Backup timer attivo e testato (restore verificato almeno una volta)
- [ ] `opencode` desktop app in esecuzione e raggiungibile su `ATTACH_URL`
- [ ] Disclaimer "non è consulenza finanziaria" visibile (già in login.html)
- [ ] Firewall: esporre solo 80/443 (e 22), **non** 8000 né 5432

### Firewall consigliato
```bash
sudo ufw allow 22,80,443/tcp
sudo ufw enable
```
