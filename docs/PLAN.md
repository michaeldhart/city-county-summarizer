# Plan

Personal CLI app that monitors Boone County, IL government meetings. Run manually.

## Commands

```
ccs summary           # rebuild general_summary.md from sources
ccs report            # generate reports/YYYY-MM.md (recap + lookahead)
ccs ingest <meeting>  # one-off: pull a specific meeting's docs + transcript
```

## Outputs

```
general_summary.md           # living source of truth, rebuilt on demand
reports/YYYY-MM.md           # monthly: recap of past meetings + lookahead
data/meetings/<id>/          # per-meeting cache: agenda.pdf, minutes.pdf, transcript.vtt, summary.md
data/manifest.json           # {meeting_id: {date, body, ingested_at, video_id, ...}}
```

Manifest makes monthly runs incremental — we only summarize meetings not yet in it.

## Sources (per docs/SOURCES.md)

Primary:
- **Diligent Community** (`boonecountyil.community.diligentoneplatform.com`) — structured JSON API for agendas, packets, member rosters. Replaced BoardDocs in May 2026; see `docs/DILIGENT_MIGRATION.md`.
- **boonecountyil.gov** — fallback minutes archive, department/member info.
- **YouTube** — meeting videos and captions (channel `UCJd8c3sZs98mx9vznx9nsOg` — Boone County Government).

Secondary (general summary only, one-time):
- Wikipedia, Ballotpedia — county overview, elected officials.
- Illinois State Archives (IRAD) — historical structure.
- 55 ILCS 5 (Counties Code) — statutory grounding.

## Pipeline per meeting

1. Discover from Diligent (list of meetings for tracked bodies per `SCOPE.md`).
2. Download agenda HTML + attached PDFs.
3. Find matching YouTube video by title/date heuristic.
4. Pull captions with `yt-dlp --write-auto-sub --sub-lang en --skip-download`.
   - If no captions: log it. Whisper fallback is a v2 decision, not v1.
5. Send (agenda + minutes + transcript) to Claude → per-meeting summary.
6. Write `data/meetings/<id>/summary.md`, update manifest.

Monthly report = concatenated summaries grouped by body + agenda-only summaries for upcoming meetings.

## General summary contents

- How county government works (structure, COTW model, meeting cadence)
- Current board members and districts
- Standing committees and sub-bodies (from `SCOPE.md`)
- Department directory with leads
- Clerk and key officials
- Links to canonical sources

Rebuilt only when you run `ccs summary`.

## Stack

- Python 3.9+ (developed on 3.9)
- `requests` for HTTP; Diligent exposes a clean JSON API, no Playwright/JS needed
- `beautifulsoup4` for HTML parsing on the CD/SWCD WordPress sites
- `yt-dlp` for video metadata + captions
- `pypdf` or `pdfplumber` for agenda/minutes PDFs
- Anthropic SDK (claude-opus-4-7 or claude-sonnet-4-6) for summarization
- Outputs are Markdown; manifest is JSON. No DB.

## Anthropic API key

The summarizer needs an API key. Get one at https://console.anthropic.com/ → Settings → API Keys.
Set it in `.env` (gitignored):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Rough cost expectation: each meeting summary is ~10–50k input tokens (agenda + minutes + transcript) and a few hundred output tokens. With Sonnet 4.6 that's well under a dollar per meeting; with Opus 4.7 a few dollars. We'll start with Sonnet and only escalate if quality is poor.
