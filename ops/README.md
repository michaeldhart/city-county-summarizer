# Running the weekly edition on `wally`

`wire-run.sh` is the Monday chain: `sync` → `brief` → `front-page` →
`build-site`, then a commit and a push. The push to `main` touches
`website/**`, which is what triggers `pages.yml` to build and deploy. Nothing
here runs Jekyll — Actions owns the build. `notify-facebook` runs last, after
the push, and no-ops until the page is public — see below.

The Mac must not run this chain. `ccs front-page` takes its issue number from
`max(existing) + 1` scanned from `_front_pages/`, so two publishers race and
produce two issues with the same number.

## Install

Give the box its own commit identity. Nothing delivers to the address — git
does not send mail and GitHub only uses it to link a commit to an account, which
is exactly what is not wanted here. A weekly edition is not authored by a person,
and a commit carrying a human's name would say it was:

    git config user.name "Wally"
    git config user.email "wally@wally.local"

Install the units. The script fills in the run-as user, their home and the
repo path, writes the three files to `/etc/systemd/system`, and reloads systemd:

    ./ops/install-units.sh

Run it as the user that owns the clone, not under `sudo` — it calls `sudo`
itself only for the writes. It refuses to run if it resolves the run-as user to
root.

Optional alert endpoint — any URL that accepts a POST body (ntfy, Discord,
Slack):

    echo 'WIRE_ALERT_URL=https://ntfy.sh/your-private-topic' \
        | sudo tee /etc/belvidere-wire-alert.conf >/dev/null
    sudo chmod 600 /etc/belvidere-wire-alert.conf

Optional Facebook posting — leave this file absent for now; `notify-facebook`
no-ops silently without it, which is the intended state until the page is
ready to go public. When it is, drop in the Page id and a Page access token:

    printf 'FACEBOOK_PAGE_ID=...\nFACEBOOK_PAGE_TOKEN=...\n' \
        | sudo tee /etc/belvidere-wire-facebook.conf >/dev/null
    sudo chmod 600 /etc/belvidere-wire-facebook.conf
    sudo systemctl daemon-reload

The next Monday run picks it up automatically — no code or unit change
needed, just `daemon-reload` so the service re-reads its `EnvironmentFile`.

## Keeping the units in sync

The install loop copies the unit files; it does not link them. The scripts are
the other way round — the units name them by absolute path, so `wire-run.sh` and
`notify-failure.sh` are picked up from the repo on every run and a `git pull` is
the whole update.

So the loop needs re-running only when a pull changes one of the three unit
files, when a new one is added, or when the user or the repo path changes. The
alert URL is not one of these: `/etc/belvidere-wire-alert.conf` is read fresh at
every start.

Rather than remembering, ask:

    ./ops/check-units.sh

It re-renders the units and diffs them against what is installed, so it answers
the question rather than relying on you to have noticed the pull. It prints
`units match the repo` and exits 0 when they agree, or names each stale file and
exits 1. Both scripts share `ops/units-lib.sh`, so the check always renders
exactly what the install would write — two copies of that `sed` would eventually
disagree and report drift that was not there.

`install-units.sh` also covers the two things `daemon-reload` does not do on its
own, whenever the timer is already enabled: it `reenable`s it, because reloading
re-reads units but does not rewrite the enable symlinks, and it restarts it so a
changed `OnCalendar` is actually re-armed. Then it prints the next fire time
rather than leaving you to trust it.

A schedule change is tidier as a drop-in than as an edit to the tracked unit —
`sudo systemctl edit belvidere-wire.timer` writes an override holding only what
differs, which survives later pulls.

## Verify before enabling the timer

    ./ops/wire-run.sh --dry-run          # runs the chain, shows the diff, commits nothing
    sudo systemctl start belvidere-wire  # a real run, under systemd
    journalctl -u belvidere-wire -n 50

The dry run still costs money — `sync` and `brief` make Claude calls, and the
issue it builds is thrown away. It skips the commit and push, then restores
`website/` so the next real run does not abort on a dirty tree. What it writes
under `data/` is kept, so the `brief` fingerprints mean the real run does not
pay twice.

Then:

    sudo systemctl enable --now belvidere-wire.timer
    systemctl list-timers belvidere-wire.timer

## Checking on it

    systemctl list-timers belvidere-wire.timer   # when it next fires
    journalctl -u belvidere-wire -n 100          # last run
    journalctl -u belvidere-wire --since '2 weeks ago' | grep '^==='

## When it fails

A failed run leaves the tree clean and the lock released; the next step is
usually to read the journal and re-run by hand. The one state needing
attention is a dirty tree — the script refuses to start on one, because a
half-finished run's generated files would otherwise be committed as an
edition.

`ccs summary` is deliberately not in the chain. It costs ~$0.40 and rebuilds
rosters that only change at reorganizations; run it by hand a few times a year.
