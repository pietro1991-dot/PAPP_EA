#!/usr/bin/env bash
# Backup di Postgres con rotazione. Legge le credenziali da .env (DATABASE_URL).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f .env ] && . ./.env
set +a

# Estrae le credenziali da DATABASE_URL e le espone come variabili PG* per pg_dump.
eval "$(python3 - <<'PY'
import os, urllib.parse as u
url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
p = u.urlparse(url)
print(f'export PGUSER={p.username}')
print(f'export PGPASSWORD={p.password}')
print(f'export PGHOST={p.hostname}')
print(f'export PGPORT={p.port or 5432}')
print(f'export PGDATABASE={p.path.lstrip("/")}')
PY
)"

BACKUP_DIR="${BACKUP_DIR:-$HOME/papp_backups}"
RETENTION="${BACKUP_RETENTION:-14}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/papp_ea_${STAMP}.sql.gz"

pg_dump | gzip > "$OUT"
# Conserva solo gli ultimi $RETENTION backup.
ls -1t "$BACKUP_DIR"/papp_ea_*.sql.gz 2>/dev/null | tail -n +"$((RETENTION + 1))" | xargs -r rm -f
echo "Backup creato: $OUT"
