#!/usr/bin/env bash
# Do the installed units still match the repo? Exits non-zero on drift.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/units-lib.sh"

drift=0
for f in "${UNITS[@]}"; do
    if ! diff -q <(render_unit "$f") "$UNIT_DIR/$f" >/dev/null 2>&1; then
        echo "needs reinstall: $f"
        drift=1
    fi
done

if (( drift )); then
    echo
    echo "Run ./ops/install-units.sh to bring $UNIT_DIR up to date."
    exit 1
fi
echo "units match the repo"
