#!/usr/bin/env bash
#
# Daily dump of Listmonk's Postgres database. The subscriber list is the
# first real PII this project holds, and unlike everything else here it
# doesn't live in git — dumps land outside the repo entirely, since
# committing one would mean committing subscriber email addresses.
set -euo pipefail

BACKUP_DIR="${LISTMONK_BACKUP_DIR:-/opt/listmonk/backups}"
CONTAINER="${LISTMONK_DB_CONTAINER:-listmonk_db}"
RETENTION_DAYS="${LISTMONK_BACKUP_RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date +%Y%m%d-%H%M%S)"
out="$BACKUP_DIR/listmonk-$stamp.dump"

# -Fc (custom format): compressed, and restorable selectively with pg_restore,
# unlike a plain SQL dump.
docker exec "$CONTAINER" pg_dump -U listmonk -Fc listmonk > "$out"
chmod 600 "$out"

echo "wrote $out ($(du -h "$out" | cut -f1))"

find "$BACKUP_DIR" -name 'listmonk-*.dump' -mtime "+$RETENTION_DAYS" -print -delete
