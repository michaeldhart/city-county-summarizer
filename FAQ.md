# FAQ

Questions that come up while using `ccs`. Add new entries at the bottom.

## If I run `ccs report` more than once in the same month, does it overwrite the existing report or make a new one?

**Same file, overwritten.** The report filename is derived from today's
month: `reports/{today YYYY-MM}.md`. If you re-run today, tomorrow, or any
day still in the current month, any newly-available meetings get folded
into the same file — replacing what was there. If you re-run in a new
month, you'd get a fresh `reports/YYYY-MM.md`.

**Why meetings that have already happened might still be missing:** the
recap only lists meetings that BoardDocs has published. The county's
BoardDocs "active meetings" tends to lag YouTube by ~2 months — so even
though a recent meeting was streamed live and is on the YouTube channel,
its agenda may not be posted on BoardDocs yet. The report has no way to
summarize a video without an agenda to pair it with.

**Once a meeting is summarized** (found in BoardDocs, ingested, added to
`data/manifest.json`), the manifest short-circuits future runs — Claude
won't re-summarize it. Repeated re-runs are essentially free for
previously-seen meetings; only newly-appeared ones cost tokens.

**One caveat with the overwrite:** if BoardDocs eventually publishes an
older meeting after the current month's report was already written,
re-running only pulls it in if the meeting date still falls inside the
recap window (default: last 35 days). Otherwise widen the window
explicitly:

```bash
ccs report --since 2026-06-01
```
