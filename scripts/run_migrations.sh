#!/usr/bin/env bash
set -euo pipefail

# Convenience script to run Alembic migrations and the legacy->ORM migration script
# Usage:
#   ./scripts/run_migrations.sh --help
# Examples:
#   # Dry-run the legacy migration against a cloned DB
#   ./scripts/run_migrations.sh --dry-run --src /path/to/clone.db
#
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

show_help() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run] [--apply] [--src PATH]

Options:
  --dry-run     Run the legacy migration script in dry-run mode (default)
  --apply       Apply the legacy migration (make sure you have a backup!)
  --src PATH    Path to the source sqlite DB to migrate. If omitted, uses
                './giocatori.db' in the repo root.

This script helps run the repository Alembic migrations and then optionally
executes the legacy DB migration script `scripts/migrate_legacy_to_orm.py`.
It creates a temporary alembic.ini on-the-fly to point Alembic at the
selected SQLite file.
EOF
}

DRY_RUN=true
APPLY=false
SRC_DB="$REPO_ROOT/giocatori.db"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help) show_help; exit 0 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --apply) DRY_RUN=false; APPLY=true; shift ;;
    --src) SRC_DB="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; show_help; exit 2 ;;
  esac
done

if [[ ! -f "$SRC_DB" ]]; then
  echo "Source DB not found: $SRC_DB" >&2
  exit 2
fi

ABS_SRC_DB="$SRC_DB"

TMP_ALEMBIC_INI="$REPO_ROOT/alembic_tmp.ini"

# If a repo-level alembic.ini exists, copy it and update only the sqlalchemy.url
if [[ -f "$REPO_ROOT/alembic.ini" ]]; then
  cp "$REPO_ROOT/alembic.ini" "$TMP_ALEMBIC_INI"
  # Update or append sqlalchemy.url in the [alembic:runtime] section
  # Use a quoted heredoc to avoid shell interpolation issues
  python3 - "$ABS_SRC_DB" "$REPO_ROOT/alembic.ini" "$TMP_ALEMBIC_INI" <<'PY'
import sys, configparser
src_db = sys.argv[1]
src_ini = sys.argv[2]
dst_ini = sys.argv[3]
cfg = configparser.ConfigParser()
cfg.read(src_ini)
if not cfg.has_section('alembic:runtime'):
    cfg.add_section('alembic:runtime')
cfg.set('alembic:runtime','sqlalchemy.url',f'sqlite:///{src_db}')
with open(dst_ini, 'w') as f:
    cfg.write(f)
PY
else
  cat > "$TMP_ALEMBIC_INI" <<EOF
[alembic]
script_location = alembic

[alembic:runtime]
sqlalchemy.url = sqlite:///$ABS_SRC_DB
EOF
fi

echo "Running Alembic migrations against: $ABS_SRC_DB"
alembic -c "$TMP_ALEMBIC_INI" upgrade head

echo "Alembic migrations complete."

if [[ "$APPLY" = true ]]; then
  echo "Running legacy -> ORM migration (apply mode) against: $ABS_SRC_DB"
  PYTHONPATH="$REPO_ROOT" python3 "$REPO_ROOT/scripts/migrate_legacy_to_orm.py" --apply --src "$ABS_SRC_DB"
else
  echo "Running legacy -> ORM migration (dry-run) against: $ABS_SRC_DB"
  PYTHONPATH="$REPO_ROOT" python3 "$REPO_ROOT/scripts/migrate_legacy_to_orm.py" --src "$ABS_SRC_DB"
fi

echo "Cleaning up temporary files: $TMP_ALEMBIC_INI"
rm -f "$TMP_ALEMBIC_INI"

echo "Done."
