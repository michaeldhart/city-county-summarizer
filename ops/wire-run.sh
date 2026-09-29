#!/usr/bin/env bash
#
# The weekly edition: sync → brief → front-page → build-site, commit, push,
# notify-facebook, notify-listmonk. GitHub Actions (pages.yml) picks up the
# push and deploys. The two notify steps wait for that deploy, run after the
# push so a dead credential never holds up the site, run independently of each
# other, and fail the run loudly if either IS configured and breaks — see
# FACEBOOK_PAGE_ID/FACEBOOK_PAGE_TOKEN
# and LISTMONK_API_URL/LISTMONK_API_USER/LISTMONK_API_TOKEN/LISTMONK_LIST_ID/
# LISTMONK_FROM_EMAIL in ops/README.md.
#
# The whole body lives in main() because this script is inside the repo it
# pulls. Bash reads a script incrementally, so a pull that rewrote these lines
# mid-run would resume at that byte offset in the new file. A function is
# parsed whole before any of it executes.
set -euo pipefail

REPO="${WIRE_REPO:-$HOME/city-county-summarizer}"
CCS="$REPO/.venv/bin/ccs"
LOCK="$HOME/.cache/belvidere-wire.lock"
# A pages.yml deploy normally takes a few minutes; this is the give-up point.
DEPLOY_WAIT_SECS=1800

main() {
    local dry_run=0
    [[ "${1:-}" == "--dry-run" ]] && dry_run=1

    # manifest.upsert is load-mutate-save with no locking: two overlapping runs
    # silently drop each other's records. The timer can't overlap itself, but a
    # hand-run during a timer run can.
    command -v flock >/dev/null || { echo "error: flock not found" >&2; exit 1; }
    mkdir -p "$(dirname "$LOCK")"
    exec 9>"$LOCK"
    if ! flock -n 9; then
        echo "error: another run holds $LOCK — refusing to start a second" >&2
        exit 1
    fi

    cd "$REPO"
    [[ -x "$CCS" ]] || { echo "error: no ccs at $CCS" >&2; exit 1; }

    if [[ -n "$(git status --porcelain)" ]]; then
        echo "error: working tree is dirty — a previous run probably died partway." >&2
        git status --short >&2
        exit 1
    fi

    echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') — pulling"
    if ! git pull --rebase origin main; then
        git rebase --abort 2>/dev/null || true
        echo "error: rebase onto origin/main failed; tree left clean" >&2
        exit 1
    fi

    echo "=== sync"
    "$CCS" sync

    echo "=== brief"
    "$CCS" brief

    echo "=== front-page"
    local front_out issue
    front_out="$("$CCS" front-page)"
    echo "$front_out"
    issue="$(sed -n 's/^Published No\. \([0-9][0-9]*\) .*/\1/p' <<<"$front_out")"
    if [[ -z "$issue" ]]; then
        echo "error: front-page did not report an issue number" >&2
        exit 1
    fi

    echo "=== build-site"
    "$CCS" build-site

    git add -A website/
    if git diff --cached --quiet; then
        echo "=== no site changes — nothing to publish"
        exit 0
    fi

    if (( dry_run )); then
        echo "=== dry run — would publish No. $issue:"
        git diff --cached --stat
        # Put website/ back, or the next real run aborts on a dirty tree. Only
        # generated files are discarded: -fd leaves gitignored _site/ alone.
        git restore --source=HEAD --staged --worktree -- website/
        git clean -fdq website/
        echo "=== dry run — website/ restored, nothing committed"
        exit 0
    fi

    echo "=== publishing No. $issue"
    git commit -q -m "Run No. $issue"
    git push -q origin main
    echo "=== pushed; pages.yml will deploy"

    # Both notify steps link to the new issue, which 404s until pages.yml has
    # deployed it. Facebook scrapes the link once, at post time, and caches
    # the "Page not found" preview it gets back — so wait for the page.
    local url status=0
    url="$(printf 'https://belviderewire.com/issues/%03d/' "$issue")"
    echo "=== waiting for $url"
    if ! wait_for_deploy "$url"; then
        echo "error: $url still not live after ${DEPLOY_WAIT_SECS}s — skipping facebook" >&2
        status=1
    else
        # Each notify step runs regardless of the other: a dead Page token must
        # not stop the mailing. A failure still fails the run, after both.
        echo "=== facebook"
        "$CCS" notify-facebook "$issue" || status=1
    fi

    echo "=== listmonk"
    "$CCS" notify-listmonk "$issue" || status=1

    exit "$status"
}

wait_for_deploy() {
    local deadline=$(( SECONDS + DEPLOY_WAIT_SECS ))
    until curl -fsS -o /dev/null "$1" 2>/dev/null; do
        (( SECONDS < deadline )) || return 1
        sleep 30
    done
}

main "$@"
