#!/usr/bin/env bash
# Called by belvidere-wire-failure@.service when a run fails. The point is that
# a headless box cannot fail quietly: ccs has no retry or backoff, so a single
# transient 500 ends the week's edition.
set -euo pipefail

unit="${1:-belvidere-wire.service}"
log="$(journalctl -u "$unit" -n 40 --no-pager 2>/dev/null || echo '(no journal)')"

echo "$unit failed at $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "$log"

if [[ -n "${WIRE_ALERT_URL:-}" ]]; then
    printf 'The Belvidere Wire: %s failed\n\n%s\n' "$unit" "$log" \
        | curl -fsS -H "Title: Wire run failed" --data-binary @- "$WIRE_ALERT_URL" \
        || echo "warning: alert POST to WIRE_ALERT_URL failed" >&2
fi
