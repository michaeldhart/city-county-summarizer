# AGENTS.md

Context and gotchas for AI agents working in this repo. `README.md` is for
humans; this file is for you. If it duplicates something in `README.md`,
`docs/PLAN.md`, or `docs/SPIKE_NOTES.md`, prefer this file — it's the "what
I'll actually trip on" digest.

## Cost discipline

- Every `ccs report` on a fresh manifest costs real money. A busy month with
  ~15 new meetings is ~$1–$2 at Sonnet 4.5 rates.
- Never run `ccs report` "just to test." If you need to smoke-test the report
  pipeline, either (a) use a narrow window that yields zero meetings, or (b)
  pre-seed `data/manifest.json` with a `MeetingRecord` pointing at an already-
  summarized meeting on disk, so the render short-circuits.
- `ccs summary` is one Claude call, ~$0.10 — safer to run, but still not free.
- If you're debugging prompts, edit the raw materials in `data/meetings/<id>/`
  and call `summarize._call_claude()` directly with a hand-built prompt rather
  than re-running the ingest pipeline.

## Python 3.9 constraint

- The user's system Python is 3.9. `pyproject.toml` says `>=3.9`.
- Every module MUST start with `from __future__ import annotations` — pipe
  union syntax (`X | None`) in annotations only parses under 3.9 with that
  import. Adding a new module without it will break imports.
- Do NOT use pipe syntax at runtime (e.g., `isinstance(x, int | str)`) — that
  needs 3.10+.

## BoardDocs quirks

- All BoardDocs endpoints require `Content-Type: application/x-www-form-urlencoded`
  POSTs with realistic browser headers (see `config.BOARDDOCS_HEADERS`).
  CloudFront returns 403 for bare curl / missing `Origin` + `Referer`.
- The `id=` parameter on `BD-GetMeeting`, `BD-GetAgenda`, `BD-GetAgendaItem`,
  `BD-GetPublicFiles` takes the SHORT `unique` (e.g., `DSCKED517FD7`), not the
  long `unid`. Using `unid` returns `"No Access"` — silent failure mode.
- All Boone County meetings live under a single `current_committee_id`
  (`AAL6YS173AC9` — "Main Governing Board"). Sub-bodies (ZBA, Health, etc.)
  do NOT have separate committee IDs — they're differentiated by meeting title.
- `boonecountyil.gov` and BoardDocs both lag reality. Recent meetings often
  don't have their agendas published for weeks after the meeting occurs.

## yt-dlp

- Always pass `--extractor-args 'youtube:player_client=android'`. Without it,
  yt-dlp errors with "The page needs to be reloaded" on captioned videos.
- County meeting videos live on the channel's `/streams` tab (archived live
  streams), not `/videos`. `list_streams()` handles this — don't switch it.
- Only Board and the two COTWs are streamed. Sub-body meetings (Zoning,
  Planning, Health, LEPC, Veterans, Ag Easement) have no video. Don't add
  a Whisper fallback expecting to find them.

## Manifest paths

- `MeetingRecord.summary_path` is stored relative to `REPO_ROOT`, not
  `DATA_DIR`. Read as `REPO_ROOT / record.summary_path`. This bit me once —
  a bad path fix is in the git history if you need context.
- Meeting IDs are `<source>:<key>`:
  - `boarddocs:<short_unique>` — recap
  - `boarddocs-preview:<short_unique>` — lookahead (kept separate so a preview
    doesn't block a later recap of the same meeting)
  - `boarddocs-cancelled:<short_unique>` — cancelled meeting, no Claude call
  - `bccd:YYYYMMDD`, `swcd:YYYYMMDD` — CD sites, date-keyed

## Files vs. git

- `data/` is fully gitignored (cached scraped materials, transcripts,
  summaries, manifest). Don't `git add` anything under it.
- `reports/*.md` and `general_summary.md` ARE tracked. Regenerating them
  produces small diffs each time — that's intentional.
- `.env` is gitignored; `.env.example` is not.

## Package layout

```
src/ccs/
  config.py     canonical body registry, SCOPE.md parsing, HTTP headers
  boarddocs.py  meetings list, agenda, item detail, attached files
  youtube.py    channel enumeration, video matching, VTT cleanup
  bccd.py       Boone Conservation District WP scraper
  swcd.py       Soil & Water Conservation District WP scraper
  pdftext.py    shared PDF download + text extraction
  manifest.py   MeetingRecord + JSON persistence
  summarize.py  three ingest entry points (BD recap, BD lookahead, CD)
  report.py     discovery + Markdown rendering for monthly reports
  general.py    `ccs summary` generator
  cli.py        argparse entry (`ccs summary` / `report` / `ingest`)
```

- `summarize.py` is the per-meeting ingest; `report.py` is the
  cross-source orchestration. Don't cross those wires.
- Prompts live inline in `summarize._build_*_prompt` and
  `general._build_prompt`. Change them there.
- The Claude model is a single constant: `config.CLAUDE_MODEL`. To try a
  different model, change it there — don't scatter model choices per call site.

## What's NOT built

- No test suite. Smoke tests are ad-hoc Python scripts against real endpoints.
- No retry / backoff on HTTP failures — a transient 500 will crash the run.
  Fine for now (personal use, low-frequency).
- No dedup across "boarddocs-preview" and "boarddocs" for the same meeting.
  Preview stays in `data/meetings/boarddocs-preview_<unique>/` after the
  recap version is written. Not a bug, just an untidied artifact.
- No OCR. If a CD site posts a scanned image PDF, `pdfplumber` returns
  nothing and the summary notes "no agenda available."

## Style rules

- Follow the codebase's existing style — no comments unless the "why" is
  non-obvious, no docstrings that just restate the function signature, no
  premature abstractions, no error handling for scenarios that can't happen.
- User prefers concise responses. Don't restate what the diff shows.
- User has said to commit only when explicitly asked. Never `git commit`
  without a clear instruction.
