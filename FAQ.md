# FAQ

Questions that come up while using `ccs`. Add new entries at the bottom.

## If I run `ccs sync` more than once, does it re-summarize meetings it already has?

**No.** `data/manifest.json` is authoritative for "did we ingest this?" Once
a meeting has been discovered, summarized and recorded there, later runs
short-circuit on it — no Claude call, no cost. Only meetings that are new to
the manifest are summarized, so repeat runs over the same window are
essentially free. `ccs ingest <source:key>` is the deliberate exception: it
re-summarizes one meeting whatever the manifest says.

**Why meetings that have already happened might still be missing:** a meeting
is only picked up once its agenda has been published on the Diligent Community
portal. The county sometimes doesn't publish an agenda until close to (or right
after) the meeting date, and there's no way to summarize a video without an
agenda to pair it with. If a meeting appears on YouTube but not on the site,
wait a few days for the agenda, then re-run.

**One caveat with the window:** `--since` defaults to 35 days ago, so a
late-published meeting drops out of reach once that default window moves past
it. Widen it explicitly:

```bash
ccs sync --since 2026-06-01
```

Then `ccs build-site` to get the newly-ingested meetings onto the site.

## If I run `ccs front-page` more than once, does it overwrite the issue or make a new one?

**A new one, every time.** Each run writes the next numbered issue to
`website/_front_pages/NNN.md` and copies it over `website/index.md`. The number
is derived by scanning that directory for the highest existing one and adding
1 — there's no counter to keep in sync. The previous issue isn't overwritten;
it stays published at `/issues/NNN/` and listed on `/issues/`.

So only `website/index.md` is replaced, which makes a bad edition disposable
rather than permanent: delete `website/_front_pages/003.md`, run again, and you
get a new No. 3 rather than a No. 4 with a hole behind it.

To put an earlier issue back on the front page — no Claude call, no new number:

```bash
ccs front-page --publish 2
```
