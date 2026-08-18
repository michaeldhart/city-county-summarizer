# V1 Spike Notes

End-to-end validation of the pipeline on the April 16, 2026 Boone County Board Meeting, plus reconnaissance on sub-bodies and the two CD sites.

Artifacts: `data/spike/board-20260416/` and `data/spike/zba-20260428/`.

> **Historical note (Aug 2026):** The county migrated off BoardDocs to the
> Diligent Community platform around May 4, 2026 — the old
> `go.boarddocs.com/il/boone` URL still serves cached historical data
> (2011 → May 4, 2026) but no new meetings appear there. The v1 pipeline
> now uses [`src/ccs/diligent.py`](../src/ccs/diligent.py) instead. See
> [DILIGENT_MIGRATION.md](DILIGENT_MIGRATION.md) for the new-platform recon.
> The BoardDocs notes below remain accurate for that platform's shape and
> are kept for context.

## What worked

### BoardDocs is fully scrapable with plain HTTP
- **No Playwright needed.** Plain `POST` requests with a real `User-Agent` + `Origin: https://go.boarddocs.com` + `Referer` headers return the JSON/HTML directly. CloudFront blocks bare curl, but honest browser headers pass.
- **Single "committee" ID (`AAL6YS173AC9`, "Main Governing Board") covers ALL bodies** on BoardDocs: County Board, both COTWs, Regional Planning, ZBA, Board of Health, Ag Easement, Veteran's Assistance, LEPC. Sub-bodies do NOT have separate committee IDs.
- Endpoint pattern (all POST, `application/x-www-form-urlencoded`, param `id=<short_unique>&current_committee_id=AAL6YS173AC9`):
  - `BD-GetMeetingsList` — full JSON list, ~1500 meetings total, ~275 KB. Only takes `current_committee_id`.
  - `BD-GetMeeting` — HTML with name, date, description, member list.
  - `BD-GetAgenda` — HTML with categories and item stubs (each with `unique` and `unid`).
  - `BD-GetAgendaItem` — HTML with subject, type, recommended action, motion text.
  - `BD-GetPublicFiles` — HTML with `<a>` links to attached PDFs (minutes, resolutions, backup).
- **Important:** `id=` uses the SHORT `unique` (e.g., `DSCKED517FD7`), not the long `unid`.

### YouTube captions are usable
- Videos live on the **`/streams` tab**, not `/videos` — they're archived live streams.
- Only County Board and the two COTWs are recorded. Sub-bodies have no video.
- `yt-dlp` with `--extractor-args 'youtube:player_client=android'` bypasses the "page needs to be reloaded" error the default client hits.
- Auto-captions have typos ("algiance") but proper nouns and dollar amounts come through cleanly.
- 84-minute meeting → 71 KB / ~13.5k words / ~18k tokens plain-text transcript.

### Claude summary quality is good on first try
- 27k input tokens, 1.6k output → ~$0.08 per meeting with Sonnet 4.5.
- Correctly captured: a 5-5 tie vote and reconsideration on a solar farm SUP, $1.9M and $2.3M road contracts, per diem debate, remote-participation approvals, absent chairman, individual member names and vote changes.
- See `data/spike/board-20260416/summary.md`.

### CD / SWCD sites are trivial
- Both are WordPress pages with `<a href>` links to PDFs, one per agenda / minutes doc.
- URL pattern: `/wp-content/uploads/YYYY/MM/{date}-meeting-{agenda|minutes}.pdf`.
- Pipeline: fetch page → parse links → download PDFs → extract text with `pdfplumber` → summarize.

## What we learned — plan changes

1. **Stack drops Playwright.** Just `requests` + `beautifulsoup4` + `pdfplumber` + `yt-dlp` + `anthropic`. Update `docs/PLAN.md`.
2. **Committee ID is a constant.** `AAL6YS173AC9` hard-coded is fine — one config value, not a dynamic lookup.
3. **Body detection is by meeting title, not committee.** Meetings all sit under one committee ID, so we filter by keywords in the title (`"Boone County Board Meeting"`, `"Committee of the Whole - Finance"`, `"Zoning Board of Appeals"`, etc.). Add a title→body mapping to config.
4. **Sub-body meetings have no video.** Their summary is agenda + agenda item details + attached PDFs (previous meeting minutes are attached to the current meeting's "Minutes" agenda item). Skip the transcript step entirely.
5. **BoardDocs lag is real.** As of "today" (2026-07-24), BoardDocs' most recent listed meeting is May 4, 2026, but YouTube has streams through July 16, 2026. The county publishes videos faster than agendas roll off the "active" view. Not a blocker but worth logging when a video exists without a matching BoardDocs meeting.
6. **Minutes come from the NEXT meeting.** BoardDocs meetings don't have minutes attached — they're published as PDFs on the *following* meeting's "Approval of Minutes" agenda item. To get a meeting's minutes, look at the next same-body meeting's Minutes item files.

## Open items before v1 proper

- **PDF extraction on sub-bodies.** We haven't actually run `pdfplumber` on a real minutes PDF yet. Assume it works (agenda PDFs are almost always text-based), but confirm on first real run.
- **Body-title matching.** Titles have inconsistent prefixes ("CANCELLED", "CANCELLED/RESCHEDULED", occasional typos like "Committtee"). Regex needs to be forgiving.
- **General summary sourcing.** BoardDocs meeting descriptions contain the full board member roster — cheaper than scraping the boonecountyil.gov member pages. Plan on that as the source of truth.

## v1 build order (proposed)

1. Config module: bodies list (from `SCOPE.md`), committee ID, YouTube channel ID, output paths.
2. `boarddocs.py`: get meetings list, meeting metadata, agenda + items + attached files. HTML→text helpers.
3. `youtube.py`: find video by date+body title heuristic, pull captions, VTT→text.
4. `bccd.py` / `swcd.py`: scrape their WP pages, download PDFs, extract text.
5. `summarize.py`: assemble inputs, call Claude, write per-meeting `summary.md`.
6. `manifest.py`: track ingested meetings so runs are incremental.
7. CLI (`ccs`): `summary`, `report`, `ingest`.
8. General summary generator: pull structural sources + one-time Wikipedia/Ballotpedia grounding.
