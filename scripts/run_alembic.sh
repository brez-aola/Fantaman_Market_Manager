#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DB_URL=${DATABASE_URL:-}
if [ -z "$DB_URL" ]; then
  # fallback to local sqlite
  DB_FILE="$REPO_ROOT/giocatori.db"
  DB_URL="sqlite:///$DB_FILE"
fi

TMP_ALEMBIC_INI="$REPO_ROOT/alembic_tmp.ini"
cp "$REPO_ROOT/alembic.ini" "$TMP_ALEMBIC_INI"

python3 - "$DB_URL" "$REPO_ROOT/alembic.ini" "$TMP_ALEMBIC_INI" <<'PY'
import sys, configparser
db_url = sys.argv[1]
src_ini = sys.argv[2]
dst_ini = sys.argv[3]
cfg = configparser.ConfigParser()
cfg.read(src_ini)
if not cfg.has_section('alembic:runtime'):
    cfg.add_section('alembic:runtime')
cfg.set('alembic:runtime','sqlalchemy.url',db_url)
with open(dst_ini, 'w') as f:
    cfg.write(f)
PY

echo "Running alembic with URL: $DB_URL"
alembic -c "$TMP_ALEMBIC_INI" "$@"

rm -f "$TMP_ALEMBIC_INI"
