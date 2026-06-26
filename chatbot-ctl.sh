#!/usr/bin/env bash
# =============================================================================
# Controllo del Chatbot PAPP EA — avvia / ferma / stato a piacimento.
#
#   ./chatbot-ctl.sh start     avvia il chatbot (app + LLM + proxy pubblico)
#   ./chatbot-ctl.sh stop      ferma il chatbot (il link risponde 502)
#   ./chatbot-ctl.sh restart   riavvia
#   ./chatbot-ctl.sh status    stato servizi + porte + link pubblico
#
# Link pubblico (utenti fuori dalla VPS):  https://77.81.226.151:8095
# Nota: certificato self-signed -> il browser mostra un avviso, "Procedi comunque".
# =============================================================================
set -u

# Servizi che compongono il chatbot (ordine di avvio; lo stop e' inverso).
SERVICES=(opencode-serve.service papp-chat.service)
PUBLIC_IP="77.81.226.151"
URL_HTTPS="https://${PUBLIC_IP}"        # nginx 443 TLS self-signed -> app
URL_HTTP="http://${PUBLIC_IP}"          # nginx 80 -> app (no avviso, non cifrato)

# Le azioni che modificano i servizi usano SEMPRE sudo: `systemctl` senza privilegi
# a volte ritorna 0 senza ricaricare davvero (restart "silenzioso"). Con sudo prende
# sempre; ti verrà chiesta la password (sudo la ricorda per qualche minuto).
# Se SUDO_ASKPASS è impostato (automazioni headless) usa quello, altrimenti il terminale.
sc() {
  if [ -n "${SUDO_ASKPASS:-}" ]; then sudo -A systemctl "$@"; else sudo systemctl "$@"; fi
}

start() {
  for s in "${SERVICES[@]}"; do echo "avvio $s..."; sc start "$s"; done
  systemctl is-active --quiet nginx || { echo "avvio nginx..."; sc start nginx; }
  echo "✅ Chatbot avviato.  Link pubblico: ${URL_HTTPS}"
}

stop() {
  # ferma in ordine inverso (prima l'app, poi l'LLM)
  for (( i=${#SERVICES[@]}-1; i>=0; i-- )); do echo "fermo ${SERVICES[$i]}..."; sc stop "${SERVICES[$i]}"; done
  echo "⛔ Chatbot fermato. Il link rispondera' 502 finche' non riavvii (nginx resta su)."
}

restart() {
  # restart vero per ogni servizio (ricarica sempre il codice aggiornato)
  for s in "${SERVICES[@]}"; do echo "riavvio $s..."; sc restart "$s"; done
  sleep 3   # l'app impiega un paio di secondi a ribindare la porta
  local code; code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8090/ 2>/dev/null)
  echo "🔄 Riavviato (app HTTP ${code:-?}).  Link: ${URL_HTTPS}"
}

status() {
  echo "── Servizi ──"
  for s in "${SERVICES[@]}" nginx; do printf "  %-24s %s\n" "$s" "$(systemctl is-active "$s" 2>/dev/null || echo '?')"; done
  echo "── Porte in ascolto ──"
  ss -tln 2>/dev/null | grep -E ":8090|:8095|:34367" | sed 's/^/  /' || echo "  (nessuna)"
  local code; code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8090/ 2>/dev/null)
  echo "── App locale (127.0.0.1:8090): HTTP ${code:-no-risposta} ──"
  echo "── Link pubblici ──"
  echo "  HTTPS : ${URL_HTTPS}   (consigliato)"
  echo "  HTTP  : ${URL_HTTP}    (senza cifratura)"
}

case "${1:-status}" in
  start)   start ;;
  stop)    stop ;;
  restart) restart ;;
  status)  status ;;
  *) echo "Uso: $0 {start|stop|restart|status}"; exit 1 ;;
esac
