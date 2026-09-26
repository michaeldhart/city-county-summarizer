# Sourced by install-units.sh and check-units.sh. The substitution lives here, in
# one place, because the check is only meaningful if it renders the units exactly
# as the install did — two copies that drift apart would report drift forever.

UNITS=(belvidere-wire.service belvidere-wire.timer belvidere-wire-failure@.service)
UNIT_DIR="${WIRE_UNIT_DIR:-/etc/systemd/system}"

# SUDO_USER first: under `sudo ./install-units.sh`, $USER is root, and baking
# that into the units would run the publication as root.
WIRE_USER="${SUDO_USER:-$USER}"
WIRE_HOME="$(getent passwd "$WIRE_USER" | cut -d: -f6)"
# From the library's own location, so neither script cares about the caller's cwd.
WIRE_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

render_unit() {
    sed -e "s|__USER__|$WIRE_USER|g" \
        -e "s|__HOME__|$WIRE_HOME|g" \
        -e "s|__REPO__|$WIRE_REPO|g" \
        "$WIRE_REPO/ops/$1"
}
