# FAQ

Questions that come up while using `ccs`. Add new entries at the bottom.

## If I run `ccs report` more than once, does it overwrite the existing report or make a new one?

**Depends on the window.** The filename is derived from the recap and
lookahead dates: `reports/{since}_to_{until}.md`. Re-running with the
same `--since` and `--until` overwrites the same file. Different dates
produce different filenames — including the default behavior, where
`--since` (`today - 35`) and `--until` (`today + 30`) shift by a day
each day, so daily runs each produce a new file.

**Why meetings that have already happened might still be missing:** the
recap only lists meetings whose agendas have been published on the
Diligent Community portal. The county sometimes doesn't publish an agenda
until close to (or right after) the meeting date. The report has no way
to summarize a video without an agenda to pair it with. If a meeting
appears on YouTube but not in the report, wait a few days for the agenda
to be published, then re-run.

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
