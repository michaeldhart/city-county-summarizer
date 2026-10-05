# Running the weekly edition on `wally`

`wire-run.sh` is the Monday chain: `sync` → `brief` → `front-page` →
`build-site`, then a commit and a push. The push to `main` touches
`website/**`, which is what triggers `pages.yml` to build and deploy. Nothing
here runs Jekyll — Actions owns the build. `notify-facebook` and
`notify-listmonk` run last, after the push, and each no-ops until its own
credential is configured — see below.

Before either notify step, the script polls the new `/issues/NNN/` URL until
the deploy has made it live (up to 30 minutes). Facebook scrapes a link once,
when the post is made, and caches whatever it gets — posting straight after the
push gave issue No. 3 a "Page not found" preview. If the page never appears,
the Facebook post is skipped and the run fails, but the mailing still goes out.
The two steps are independent the same way: a dead Page token does not stop the
mailing, and either one failing fails the run after both have been tried.

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

With ntfy, install the phone app and subscribe to the same topic. The topic
name is the only secret, so make it long and random (`openssl rand -hex 12`).
Test the whole path without waiting for a real failure:

    sudo systemctl start belvidere-wire-failure@belvidere-wire.service

Optional Facebook posting — leave this file absent for now; `notify-facebook`
no-ops silently without it, which is the intended state until the page is
ready to go public. When it is, drop in the Page id and a Page access token:

    printf 'FACEBOOK_PAGE_ID=...\nFACEBOOK_PAGE_TOKEN=...\n' \
        | sudo tee /etc/belvidere-wire-facebook.conf >/dev/null
    sudo chmod 600 /etc/belvidere-wire-facebook.conf
    sudo systemctl daemon-reload

The next Monday run picks it up automatically — no code or unit change
needed, just `daemon-reload` so the service re-reads its `EnvironmentFile`.

Mailing-list send — `belvidere-wire.service` sets `LISTMONK_REQUIRED=1`, so a
missing or incomplete file makes `notify-listmonk` fail the run and fire the
alert instead of skipping silently (it did exactly that once, and a Monday
issue went unmailed). Before the list is public, drop that `Environment=` line
via a drop-in to get the old no-op back. Create the file:

    printf 'LISTMONK_API_URL=http://localhost:9000\nLISTMONK_API_USER=...\nLISTMONK_API_TOKEN=...\nLISTMONK_LIST_ID=...\nLISTMONK_FROM_EMAIL=The Belvidere Wire <wire@belviderewire.com>\n' \
        | sudo tee /etc/belvidere-wire-listmonk.conf >/dev/null
    sudo chmod 600 /etc/belvidere-wire-listmonk.conf
    sudo systemctl daemon-reload

`LISTMONK_API_URL` is `http://localhost:9000` rather than
`https://list.belviderewire.com` — `wire-run.sh` runs on wally, the same box
Listmonk is on, so the call never needs to leave the machine through the
Tunnel and back in. `LISTMONK_API_USER`/`LISTMONK_API_TOKEN` come from an
**API**-type user (Listmonk admin → Users → New, not the SMTP credentials and
not your own admin login) — that's a distinct credential scoped to the API,
so it can be revoked without touching how you log in. `LISTMONK_LIST_ID` is
the list's numeric id (`Lists` page, or `GET /api/lists`) — not the UUID the
public subscription form uses, those are two different identifiers for the
same list.

## Keeping the units in sync

The install loop copies the unit files; it does not link them. The scripts are
the other way round — the units name them by absolute path, so `wire-run.sh` and
`notify-failure.sh` are picked up from the repo on every run and a `git pull` is
the whole update.

So the loop needs re-running only when a pull changes one of the unit files,
when a new one is added, or when the user or the repo path changes. The
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
    journalctl -u belvidere-wire --since '2 weeks ago' | grep '=== '

Don't anchor that grep with `^`: journal lines start with a timestamp and
hostname, so `'^==='` matches nothing. Use `sudo` if the journal comes back
empty and you aren't in the `systemd-journal` group.

## When it fails

A failed run leaves the tree clean and the lock released; the next step is
usually to read the journal and re-run by hand. The one state needing
attention is a dirty tree — the script refuses to start on one, because a
half-finished run's generated files would otherwise be committed as an
edition.

`ccs summary` is deliberately not in the chain. It costs ~$0.40 and rebuilds
rosters that only change at reorganizations; run it by hand a few times a year.

## Listmonk backups

`listmonk-backup.timer` runs `listmonk-backup.sh` daily at 03:00, dumping the
Listmonk Postgres container (`docker exec listmonk_db pg_dump`) to
`/opt/listmonk/backups/listmonk-<timestamp>.dump` and deleting anything older
than 30 days. This is separate from the wire pipeline and the two never
overlap. The subscriber list is the first real PII this project holds, and
unlike everything else here it is deliberately kept out of git — the dumps
live outside the repo entirely, `chmod 600`, in a `chmod 700` directory.

Verify, then enable, the same way as the wire timer:

    sudo systemctl start listmonk-backup    # a real run
    journalctl -u listmonk-backup -n 20
    ls -la /opt/listmonk/backups
    sudo systemctl enable --now listmonk-backup.timer
    systemctl list-timers listmonk-backup.timer

To restore a dump:

    docker exec -i listmonk_db pg_restore -U listmonk -d listmonk --clean \
        < /opt/listmonk/backups/listmonk-<timestamp>.dump

A same-box backup does not survive wally itself dying — worth deciding
separately whether a copy should also leave the machine (synced to the Mac, a
cloud bucket, wherever), which this timer does not attempt.

Once enabled, it runs itself — no re-running anything day to day. The only
time it needs attention is the same case as the wire timer: a pull that
changes `listmonk-backup.service` or `.timer`'s own content, which needs
`./ops/install-units.sh` to reach systemd. See "Keeping the units in sync"
above — `./ops/check-units.sh` already covers both timers, so there's nothing
timer-specific to remember here.

## Status page

`status-snapshot.timer` runs `status-snapshot.py` every five minutes and writes
one self-contained page to `/var/lib/wire-status/index.html`;
`status-serve.service` serves that directory with `python3 -m http.server`.
Nothing collects live — the page is a snapshot, and it says so: it shows when it
was written and turns red if it is over 15 minutes old, which is how a dead
timer shows up. The script is stdlib-only and every section is collected
independently, so one failed probe reads "unknown" rather than blanking the page.

It covers host load/temperature/updates, memory, disk, network and DNS, the
`cloudflared` service plus an end-to-end probe through the Tunnel, Listmonk (login
page, Postgres, subscriber and subscription counts, last campaign), backup
freshness, the publishing pipeline (clean tree, `origin` reachable, latest issue
live, last Monday run), Docker containers, every timer on the box with its next
and last run, and week-long sparklines from `history.json` beside the page.

Install and start:

    ./ops/install-units.sh
    sudo systemctl enable --now status-snapshot.timer status-serve.service
    sudo systemctl start status-snapshot     # don't wait five minutes for the first page

Then open `http://wally.local:8088/` (or wally's LAN address) from any machine
on the network. There is no auth and it shows subscriber counts, so it binds the
LAN only by design — do not add it to the Tunnel's ingress. Override the bind
address or port, the tunnel probe URL, or the Listmonk DB container name in
`/etc/belvidere-wire-status.conf` (`WIRE_STATUS_BIND`, `WIRE_STATUS_PORT`,
`WIRE_STATUS_TUNNEL_URL`, `LISTMONK_DB_CONTAINER`), then
`sudo systemctl restart status-serve` / `daemon-reload` as needed.

Alerts reuse `WIRE_ALERT_URL`. A section must be down for two consecutive runs
(ten minutes) before it posts, and it posts once more when it recovers, so a
blip does not page you and a long outage does not repeat. Timers and the
pipeline do not alert from here: a failed Monday run already does through
`belvidere-wire-failure@`.

The snapshot runs as the repo user with the `docker` and `systemd-journal`
groups added by the unit. If a row reads "journal not readable" or Docker shows
"not reachable", that user is missing one of them.
