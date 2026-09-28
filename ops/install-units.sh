#!/usr/bin/env bash
# Render the unit files into /etc/systemd/system and reload systemd. Safe to
# re-run; that is how a changed unit reaches systemd, since the install copies
# the files rather than linking them.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/units-lib.sh"

if [[ "$WIRE_USER" == "root" ]]; then
    echo "error: resolved the run-as user to root. Run this as the user that owns" >&2
    echo "       the clone — plain ./ops/install-units.sh, or sudo from that user." >&2
    exit 1
fi

SUDO=sudo
[[ $EUID -eq 0 ]] && SUDO=""

echo "user=$WIRE_USER home=$WIRE_HOME repo=$WIRE_REPO"
for f in "${UNITS[@]}"; do
    render_unit "$f" | $SUDO tee "$UNIT_DIR/$f" >/dev/null
    echo "  wrote $UNIT_DIR/$f"
done

$SUDO systemctl daemon-reload

# daemon-reload re-reads units but does not rewrite the enable symlinks, and a
# changed OnCalendar needs the timer re-armed. Both are idempotent, so just do
# them whenever a given timer is already enabled; one not yet enabled (a brand
# new one, or one nobody has turned on yet) is left alone — see ops/README.md.
echo "reloaded."
for t in "${TIMERS[@]}"; do
    if systemctl is-enabled --quiet "$t" 2>/dev/null; then
        $SUDO systemctl reenable "$t" >/dev/null
        $SUDO systemctl restart "$t"
        echo "  $t: re-enabled and re-armed"
    else
        echo "  $t: not enabled yet"
    fi
done
systemctl list-timers "${TIMERS[@]}" --no-pager
