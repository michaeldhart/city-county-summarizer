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
- `ccs check` is free (only hits meeting-list endpoints, no Claude). Use it
  to preview which bodies have records in a window before spending on report.
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

## Diligent platform (current source; replaced BoardDocs in May 2026)

- Base URL: `https://boonecountyil.community.diligentoneplatform.com` — public
  REST API, no auth, no session, just a normal User-Agent.
- Key endpoints:
  - `GET /Services/MeetingsService.svc/meetings?from=YYYY-MM-DD&to=YYYY-MM-DD&loadall=false`
  - `GET /Services/MeetingsService.svc/meetings/{id}/meetingData`
  - `GET /Services/MeetingsService.svc/meetings/{id}/meetingDocuments`
  - `GET /document/{guid}` — download an attachment PDF referenced in the agenda HTML
- The whole agenda comes back as one HTML blob (rendered from a `.docx`) —
  there are no per-item detail calls. Attachments are `<a href="/document/{guid}">`
  inside that HTML; use `diligent.extract_attachments(html)` to get them.
- Body identification uses `MeetingTypeId` (int). See `config.BODIES_BY_TYPE_ID`.
  Known: 18=COTW-Admin, 19=COTW-Finance, 20=Health, 22=Board, 23=ZBA,
  29=Planning, 31=Ag Easement, 32=Enterprise Zone.
- LEPC and Veteran's Assistance have `type_id=None` — no agendas on Diligent
  yet. They stay tracked but won't match. If you find where they publish, wire it.
- The old BoardDocs URL (`go.boarddocs.com/il/boone`) still returns cached
  historical data through May 4, 2026 but no new meetings will ever appear.
  See [docs/DILIGENT_MIGRATION.md](docs/DILIGENT_MIGRATION.md) for full recon.
- The county doesn't always publish agendas in advance — a meeting can be
  on YouTube before it's on Diligent. That's NOT the old "BoardDocs lag" myth
  (which was actually a dead platform); it's a normal short publishing delay.

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
  - `diligent:<numeric_id>` — recap
  - `diligent-preview:<numeric_id>` — lookahead (kept separate so a preview
    doesn't block a later recap of the same meeting)
  - `diligent-cancelled:<numeric_id>` — cancelled meeting, no Claude call
  - `bccd:YYYYMMDD`, `swcd:YYYYMMDD` — CD sites, date-keyed

## Files vs. git

- `data/` is fully gitignored (cached scraped materials, transcripts,
  summaries, manifest). Don't `git add` anything under it.
- `reports/` is gitignored (per-run monthly reports are regenerable from
  `data/manifest.json` + sources).
- `general_summary.md` IS tracked. Regenerating it produces small diffs
  each time — that's intentional.
- `.env` is gitignored; `.env.example` is not.

## Package layout

```
src/ccs/
  config.py     canonical body registry (type_id → body), SCOPE.md parsing, HTTP headers
  diligent.py   meetings list, meeting data, agenda HTML, attachment discovery
  youtube.py    channel enumeration, video matching, VTT cleanup
  bccd.py       Boone Conservation District WP scraper
  swcd.py       Soil & Water Conservation District WP scraper
  pdftext.py    shared PDF download + text extraction
  manifest.py   MeetingRecord + JSON persistence
  summarize.py  three ingest entry points (BD recap, BD lookahead, CD)
  report.py     discovery + Markdown rendering for monthly reports
  general.py    `ccs summary` generator
  cli.py        argparse entry (`ccs summary` / `check` / `report` / `ingest`)
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
