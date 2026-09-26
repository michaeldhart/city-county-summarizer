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
# them whenever the timer is already enabled.
if systemctl is-enabled --quiet belvidere-wire.timer 2>/dev/null; then
    $SUDO systemctl reenable belvidere-wire.timer >/dev/null
    $SUDO systemctl restart belvidere-wire.timer
    echo "reloaded; timer re-enabled and re-armed"
    systemctl list-timers belvidere-wire.timer --no-pager
else
    echo "reloaded. The timer is not enabled yet — see ops/README.md."
fi
