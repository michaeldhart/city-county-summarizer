# AGENTS.md

Context and gotchas for AI agents working in this repo. `README.md` is for
humans; this file is for you. If it duplicates something in `README.md`,
`docs/PLAN.md`, or `docs/SPIKE_NOTES.md`, prefer this file — it's the "what
I'll actually trip on" digest.

## Cost discipline

- Every `ccs sync` on a fresh manifest costs real money. A busy month with
  ~15 new meetings is ~$1–$2 at Sonnet 4.5 rates; a full-year backfill across
  all five governments ran ~$25.
- Never run `ccs sync` "just to test." If you need to smoke-test the pipeline,
  either (a) use a narrow window that yields zero meetings, or (b) pre-seed
  `data/manifest.json` with a `MeetingRecord` pointing at an already-summarized
  meeting on disk, so the render short-circuits.
- To smoke-test one source end-to-end, `ccs ingest <source>:<key>` on a single
  meeting is ~$0.10 and exercises the whole path. Do that before any backfill.
- `ccs check` is free (only hits meeting-list endpoints, no Claude). Use it
  to preview which bodies have records in a window before spending on report.
- Scope any backfill with `--only <body|source|jurisdiction>`. A bare
  `ccs sync --since 2026-01-01` ingests every government at once.
- `ccs summary` is one Claude call, ~$0.10 — safer to run, but still not free.
- If you're debugging prompts, edit the raw materials in `data/meetings/<id>/`
  and call `summarize._call_claude()` directly with a hand-built prompt rather
  than re-running the ingest pipeline.

## Python 3.9 constraint

- The user's system Python is 3.9 (`/usr/bin/python3`). `pyproject.toml` says
  `>=3.9`. The deps and the editable `ccs` install live there, in
  `~/Library/Python/3.9`. Note 3.9 went EOL in Oct 2025 — a move to a supported
  interpreter is worth doing eventually, but it's a migration, not a chore.
- **Homebrew Python can shadow it.** `brew install ocrmypdf` pulls `python@3.14`
  as a dependency and links `/opt/homebrew/bin/python3`, which wins on PATH via
  `brew shellenv` in `.zshrc` — a bare `python3 -m ccs.cli` then dies with
  ModuleNotFoundError. Resolved by `brew unlink python@3.14`: ocrmypdf and
  img2pdf don't use that symlink (both ship private libexec venvs with absolute
  Cellar shebangs) and resolve through `/opt/homebrew/opt/python@3.14`, which
  unlink leaves in place. `brew doctor` will warn about an unlinked keg — that's
  expected, not a problem. A `brew upgrade` may re-link it; if `python3` is
  suddenly 3.14 again, unlink again.
- Subprocess calls inside the package must use `sys.executable`, never the
  string "python3" — otherwise they follow PATH to whatever interpreter wins.
- Every module MUST start with `from __future__ import annotations` — pipe
  union syntax (`X | None`) in annotations only parses under 3.9 with that
  import. Adding a new module without it will break imports.
- Do NOT use pipe syntax at runtime (e.g., `isinstance(x, int | str)`) — that
  needs 3.10+.

## Diligent platform (current source; replaced BoardDocs in May 2026)

- Boone County base URL: `https://boonecountyil.community.diligentoneplatform.com`
  — public REST API, no auth, no session, just a normal User-Agent.
- Every `diligent.py` function takes the tenant `base` as its first argument.
  There is no module-level base URL: the same product is served under several
  hostname families and numeric meeting ids collide between tenants, so each
  tenant gets its own `source` namespace in `sources.SOURCES`.
- Key endpoints:
  - `GET /Services/MeetingsService.svc/meetings?from=YYYY-MM-DD&to=YYYY-MM-DD&loadall=false`
  - `GET /Services/MeetingsService.svc/meetings/{id}/meetingData`
  - `GET /Services/MeetingsService.svc/meetings/{id}/meetingDocuments`
  - `GET /document/{guid}` — download an attachment PDF referenced in the agenda HTML
- The whole agenda comes back as one HTML blob (rendered from a `.docx`) —
  there are no per-item detail calls. Attachments are `<a href="/document/{guid}">`
  inside that HTML; use `diligent.extract_attachments(base, html)` to get them.
- Body identification uses `(source, MeetingTypeId)` — type ids are only
  unique within a tenant. See `config.body_for_type_id(source, type_id)`.
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
  streams), not `/videos`. Other channels upload to `/videos` instead — the
  tab is per-jurisdiction (`Jurisdiction.youtube_tab`), passed to
  `youtube.list_videos(channel_id, tab)`. Don't change Boone's.
- Only Board and the two COTWs are streamed. Sub-body meetings (Zoning,
  Planning, Health, LEPC, Veterans, Ag Easement) have no video. Don't add
  a Whisper fallback expecting to find them.

## Manifest paths

- `MeetingRecord.summary_path` is stored relative to `REPO_ROOT`, not
  `DATA_DIR`. Read as `REPO_ROOT / record.summary_path`. This bit me once —
  a bad path fix is in the git history if you need context.
- Meeting IDs are `<source>:<key>`, where `key` comes from the source:
  - `diligent:<numeric_id>` / `d100:<numeric_id>` — Diligent tenants. The
    numeric ids collide between tenants, which is why each has its own source.
  - `bccd:YYYYMMDD`, `swcd:YYYYMMDD` — one meeting per date, so date is enough.
  - `bpd:YYYYMMDD` for the regular board, `bpd:YYYYMMDD-<slug>` otherwise —
    the Park District runs a Regular meeting and a Public Hearing at the same
    date *and* time, so date alone collides.
  - PDF-index meetings supply their own `.key` and `.name`; don't rebuild the
    id from `.date` at the call site.

## Resources (the meeting page's right-hand column)

- `MeetingRecord.resources` is a list of `manifest.Resource(kind, label, url)`,
  built in `resources.py` at ingest and rendered by `_layouts/meeting.html`.
  Kinds: `portal`, `agenda`, `minutes`, `attachment`, `video`.
- **`attachment` is the odd one out: it never reaches Claude.** Diligent agendas
  link backup PDFs as `/document/{guid}`; nothing downloads them, so only the
  agenda HTML and the caption transcript are actually summarized. The layout
  lists them under a separate "Also linked from the agenda" heading that says
  so. If you ever wire those PDFs into the prompt, move them into the main
  group and delete the disclaimer — don't leave the page lying.
- Older records predate the field. `ccs backfill-resources` fills them in with
  **no Claude calls**: Diligent rebuilds offline from the cached
  `data/meetings/<id>/document_*.html`, PDF sources re-scrape their index to
  recover the minutes URL that `MeetingRecord.url` never kept. It only touches
  records with an empty list, so it can't downgrade a properly-ingested one.
- It reports a "partial" count: BPD and Belvidere index pages only show a year
  or two, so meetings older than that no longer appear and fall back to the
  single url already on the record. Re-ingesting is the only way to do better,
  and that costs money.

- **Never run two `ccs sync`/`ccs ingest` processes at once.** `manifest.upsert`
  is load-mutate-save with no locking, so concurrent runs silently drop each
  other's records.

## Files vs. git

- `data/` is fully gitignored (cached scraped materials, transcripts,
  summaries, manifest). Don't `git add` anything under it.
- `reports/` is gitignored (per-run monthly reports are regenerable from
  `data/manifest.json` + sources).
- `website/assets/main.scss` is the site's only stylesheet. It overrides the
  copy minima ships at the same path and `@import "minima"` pulls the theme in
  first, so everything in it is additive. Note `.breadcrumb`, `.jurisdiction`
  and `.count` appear in the templates but have no rules yet.
- `website/` IS tracked, including the generated `_bodies/`, `_meetings/` and
  `about/` content. Regenerating produces diffs each time — that's intentional,
  since the site is the durable archive: the Park District page drops a year
  each January and only the manifest and the published site keep it.
- `.env` is gitignored; `.env.example` is not.

## Package layout

```
src/ccs/
  config.py     jurisdiction + body registries, SCOPE.md parsing, HTTP headers
  sources.py    source namespace → client (DiligentSource / PdfIndexSource)
  diligent.py   meetings list, meeting data, agenda HTML, attachment discovery
  youtube.py    channel enumeration, video matching, VTT cleanup
  bccd.py       Boone Conservation District WP scraper
  swcd.py       Soil & Water Conservation District WP scraper
  bpd.py        Belvidere Township Park District WP scraper
  pdftext.py    shared PDF download + text extraction, OCR fallback
  manifest.py   MeetingRecord + Resource + JSON persistence
  resources.py  per-meeting source lists (portal/agenda/minutes/attachment/video)
  summarize.py  per-meeting ingest (ingest_diligent, ingest_pdf_meeting)
  report.py     cross-source discovery + ingestion orchestration
  sitegen.py    manifest → Jekyll _bodies/_meetings collections
  general.py    `ccs summary` generator
  cli.py        argparse entry (`summary` / `check` / `sync` / `ingest` /
                `backfill-resources` / `build-site`)
```

- Adding a government means three things: a `Jurisdiction` (owns the YouTube
  channel), a `sources.SOURCES` entry (owns the base URL or the lister), and
  `Body` rows pointing at both. Nothing else should learn a new hostname.

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
- OCR is a soft dependency. `pdftext.pdf_to_text` routes anything under
  `MIN_CHARS_PER_PAGE` (150) through `ocrmypdf` and caches `*.ocr.pdf`
  beside the original. If the binary is missing it warns and returns the
  thin text rather than crashing.

## Style rules

- Follow the codebase's existing style — no comments unless the "why" is
  non-obvious, no docstrings that just restate the function signature, no
  premature abstractions, no error handling for scenarios that can't happen.
- User prefers concise responses. Don't restate what the diff shows.
- User has said to commit only when explicitly asked. Never `git commit`
  without a clear instruction.
