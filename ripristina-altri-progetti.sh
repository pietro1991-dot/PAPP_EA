#!/usr/bin/env bash
# Ripristina gli altri progetti fermati il 2026-06-26 e riporta nginx allo stato originale
# (PAPP torna su :8095, l'IP nudo torna ad ai-act/MO.VE). Lanciare con sudo.
#   sudo ./ripristina-altri-progetti.sh
set -u
BK=/etc/nginx/sites-enabled.bak.20260626_155230
CONFBAK=/etc/nginx/sites-available/papp-chat.conf.bak.20260626_155230

if [ "$(id -u)" -ne 0 ]; then echo "Esegui con sudo: sudo $0"; exit 1; fi

echo "== riavvio servizi altri progetti =="
for s in pm2-pietro_giacobazzi.service packi-v2.service paki-workspace.service trading-dashboard.service; do
  systemctl enable --now "$s" 2>/dev/null && echo "  on: $s" || echo "  (problema con $s)"
done

echo "== ripristino siti nginx dal backup =="
if [ -d "$BK" ]; then
  rm -f /etc/nginx/sites-enabled/*
  cp -a "$BK"/. /etc/nginx/sites-enabled/
  [ -f "$CONFBAK" ] && cp -a "$CONFBAK" /etc/nginx/sites-available/papp-chat.conf
  nginx -t && systemctl reload nginx && echo "  ✅ nginx ripristinato (PAPP di nuovo su :8095)"
else
  echo "  ⚠️ backup $BK non trovato — ripristino nginx manuale necessario"
fi
echo "Fatto. Gli altri progetti sono di nuovo attivi."
