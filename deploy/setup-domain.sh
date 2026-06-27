#!/usr/bin/env bash
# =============================================================================
# PHAI — attivazione dominio + HTTPS valido (Let's Encrypt) in un colpo solo.
#
# Cosa fa:
#   1. crea un server block nginx per il TUO dominio (instrada per server_name,
#      NON tocca gli altri siti della VPS);
#   2. ottiene un certificato Let's Encrypt col metodo webroot (nessun downtime);
#   3. riscrive il server block con HTTPS + redirect 80->443;
#   4. imposta il rinnovo automatico.
#
# Prerequisito OBBLIGATORIO: il record DNS A del dominio deve già puntare a
# questa VPS (77.81.226.151) e propagato. Verifica con:  dig +short TUO.DOMINIO
#
# Uso:
#   sudo bash deploy/setup-domain.sh app.tuodominio.com tua@email.com
# =============================================================================
set -euo pipefail

DOMAIN="${1:?Uso: sudo bash setup-domain.sh <dominio> <email>}"
EMAIL="${2:?Serve un'email per Let's Encrypt (avvisi di scadenza)}"
APP_PORT="${APP_PORT:-8090}"
WEBROOT=/var/www/certbot
AVAIL=/etc/nginx/sites-available/phai.conf
ENABLED=/etc/nginx/sites-enabled/phai.conf

if [[ $EUID -ne 0 ]]; then echo "Esegui con sudo."; exit 1; fi

echo "==> Controllo DNS ($DOMAIN -> dovrebbe essere 77.81.226.151)"
dig +short "$DOMAIN" || true
echo "    (se sopra non vedi l'IP della VPS, ferma e aspetta la propagazione DNS)"
sleep 2

echo "==> 1/5 Webroot per la challenge ACME"
mkdir -p "$WEBROOT"; chmod 755 "$WEBROOT"

write_phase1() {
cat > "$AVAIL" <<EOF
# PHAI — fase 1 (solo HTTP, per ottenere il certificato). Generato da setup-domain.sh
map \$http_upgrade \$phai_conn_upgrade { default upgrade; '' close; }
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root $WEBROOT; }
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$phai_conn_upgrade;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
EOF
}

write_phase2() {
cat > "$AVAIL" <<EOF
# PHAI — HTTPS valido (Let's Encrypt). Generato da setup-domain.sh.
# Instrada per server_name: NON interferisce con gli altri siti della VPS.
map \$http_upgrade \$phai_conn_upgrade { default upgrade; '' close; }

server {            # HTTP -> redirect a HTTPS (+ rinnovo ACME)
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root $WEBROOT; }
    location / { return 301 https://\$host\$request_uri; }
}

server {            # HTTPS -> app PHAI su 127.0.0.1:$APP_PORT
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    # HSTS (decommenta dopo aver verificato che tutto funziona in HTTPS):
    # add_header Strict-Transport-Security "max-age=31536000" always;

    access_log /var/log/nginx/phai-access.log;
    error_log  /var/log/nginx/phai-error.log;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$phai_conn_upgrade;   # WebSocket /ws
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;   # risposte LLM lunghe
        proxy_buffering off;       # streaming SSE della chat
    }
}
EOF
}

echo "==> 2/5 Server block fase 1 (HTTP)"
write_phase1
ln -sf "$AVAIL" "$ENABLED"
nginx -t && systemctl reload nginx

echo "==> 3/5 Certificato Let's Encrypt (webroot, nessun downtime)"
certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL"

echo "==> 4/5 Server block fase 2 (HTTPS + redirect)"
write_phase2
nginx -t && systemctl reload nginx

echo "==> 5/5 Rinnovo automatico (cron giornaliero, reload nginx dopo il rinnovo)"
( crontab -l 2>/dev/null | grep -v 'certbot renew' ; \
  echo '17 3 * * * certbot renew --quiet --deploy-hook "systemctl reload nginx"' ) | crontab -

echo ""
echo "✅ FATTO. PHAI è online su:  https://$DOMAIN"
echo "   Verifica:  curl -I https://$DOMAIN"
echo ""
echo "Ora aggiorna l'EA: InpServerUrl = https://$DOMAIN (o ship un preset .set),"
echo "e di' ai clienti di autorizzare https://$DOMAIN in Strumenti>Opzioni>EA>WebRequest."
