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

Substitute the user and repo path into the units, then install them:

    export WIRE_USER=$USER
    export WIRE_REPO=$HOME/city-county-summarizer
    for f in belvidere-wire.service belvidere-wire.timer belvidere-wire-failure@.service; do
        sed -e "s|__USER__|$WIRE_USER|g" -e "s|__REPO__|$WIRE_REPO|g" "ops/$f" \
            | sudo tee "/etc/systemd/system/$f" >/dev/null
    done
    sudo systemctl daemon-reload

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

Rather than remembering, ask whether the installed copies have drifted:

    for f in belvidere-wire.service belvidere-wire.timer belvidere-wire-failure@.service; do
        diff -q <(sed -e "s|__USER__|$USER|g" -e "s|__REPO__|$HOME/city-county-summarizer|g" "ops/$f") \
                "/etc/systemd/system/$f" >/dev/null 2>&1 || echo "needs reinstall: $f"
    done

Silence means they match. Two things `daemon-reload` does not cover on its own:

- A changed `[Install]` section needs `sudo systemctl reenable belvidere-wire.timer`.
  Reloading re-reads units but does not rewrite the enable symlinks.
- After changing `OnCalendar`, `sudo systemctl restart belvidere-wire.timer` and
  then `systemctl list-timers belvidere-wire.timer` to see the new fire time
  rather than trusting it.

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
