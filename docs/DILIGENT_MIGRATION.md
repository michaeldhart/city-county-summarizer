# Diligent Platform Migration Notes

The county migrated off BoardDocs to Diligent Community around **May 4, 2026**.
BoardDocs was acquired by Diligent; many BoardDocs customers are on this
migration path.

## Root cause of the "lag" that wasn't

Prior to this migration we assumed BoardDocs was ~2 months behind reality
(spike data on 2026-07-24 showed May 4 as the newest meeting). The lag was
actually silence — the old system is frozen. Sanity check on 2026-08-17:
identical 1531 meetings, identical May 4 cutoff, real-user browser view
matches the API. Meanwhile the new Diligent portal was fully current with
meetings scheduled through September.

Old URL (frozen archive, still useful for 2011 → May 4, 2026 backfill):
- `https://go.boarddocs.com/il/boone/Board.nsf/Public`

New URL (current):
- `https://boonecountyil.community.diligentoneplatform.com`

## API endpoints

Clean REST/JSON, no auth, no session, just a normal User-Agent header:

| Endpoint | Purpose |
|----------|---------|
| `GET /Services/MeetingsService.svc/meetings?from=YYYY-MM-DD&to=YYYY-MM-DD&loadall=false` | Meeting list within date range |
| `GET /Services/MeetingsService.svc/meetings/{id}/meetingData` | Metadata + member roster |
| `GET /Services/MeetingsService.svc/meetings/{id}/meetingDocuments` | Documents: agenda HTML (`DocumentType=1`) + PDF (`DocumentType=4`) |
| `GET /api/videolink/{id}` | Video link (usually empty; use YouTube matching) |
| `GET /document/{guid}` | Download any attached PDF referenced in agenda HTML |

The old BoardDocs pattern of per-item detail calls (`BD-GetAgendaItem`) does
not exist here. The whole agenda comes back as one HTML blob, rendered from
the source `.docx`. Attachments are linked inline as `<a href="/document/{guid}">`.

## Body → `MeetingTypeId` mapping

Every meeting has a numeric `MeetingTypeId`. No more title-regex matching:

| ID | Body |
|----|------|
| 18 | Committee of the Whole Meeting - Administration |
| 19 | Committee of the Whole Meeting - Finance |
| 20 | Boone County Board of Health Meeting |
| 22 | Boone County Board Meeting |
| 23 | Boone County Zoning Board of Appeals |
| 29 | Regional Planning Commission |
| 31 | Agricultural Conservation Easement Commission |
| 32 | Enterprise Zone Advisory Committee |
| 33 | City-County Coordinating Committee |

Type 17 ("Imported Meetings: 2011-2025") is a lump for historical data
migrated in bulk from the old system: 1,491 meetings of every body under one
id. Nothing tracks it, and nothing should without title-parsing the lot.

Type 33 appeared after this recon and has one meeting scheduled (Oct 13, 2026).
There is no `Body` for it, so it is skipped rather than misfiled.

## The type ids on imported meetings are wrong (found Sep 17, 2026)

"No more title-regex matching" was true only of meetings the county created in
Diligent itself. The migration brought the last six months of BoardDocs across
separately from the 2011-2025 lump, and stamped **every one of those meetings
with type id 22, "Boone County Board Meeting"** — 33 meetings, ids 1567 through
1606, dated Nov 13, 2025 through May 4, 2026. A zoning hearing, a Board of
Health meeting and a Committee of the Whole all arrive claiming to be the
County Board. Meetings created natively after the May 4 cutover (ids 1554-1562
and 1607 up) carry the right type.

The titles survived the import intact, so they are the better evidence. Each
Diligent `Body` now carries a `title_re`, and `config.body_for_meeting()`
prefers it when it names a *different* body of the same tenant; where the title
and the id agree, or no pattern matches, the id stands. An id that maps to no
body still maps to none — rescuing type 17 by title would quietly make 1,491
historical meetings eligible for the next `ccs sync --since`.

Across all 1,571 meetings on the county tenant the override changes exactly
those 33, and none on District 100, whose bodies carry no patterns.

Fallout, repaired Sep 17, 2026: 19 manifest records had been filed under
`board`. Because only the attribution was wrong — every summary on disk was
written from the real agenda and names the real body — they were re-filed in
place from the live meetings list rather than re-ingested, and the site
regenerated. Their dispatch permalinks moved from `/bodies/board/meetings/…`
to their own beat, so the old URLs 404; no published front-page issue linked
any of them.

### Enterprise Zone (type 32)

`enterprise-zone` is now a tracked `Body` rather than being folded into the
Board or the COTWs. It is intergovernmental — Boone County, Belvidere, Poplar
Grove and Capron, with a chairmanship that rotates between them — so its
business is not the County Board's, and filing it there would repeat the
mistake above under a different name. It meets rarely (the April 9, 2026
meeting approved minutes from April 13, 2023), but a thin beat page is the
honest shape for a body that meets rarely; the alternative is a reader finding
enterprise-zone boundary decisions on a page about the County Board.

**Not visible on Diligent:** LEPC (Local Emergency Planning Committee) and
Veteran's Assistance Commission. Either they haven't migrated, they publish
elsewhere, or they don't meet often. `Body.type_id` is `None` for both in
`config.py`; they'll never match. If we discover where those bodies publish,
add the source.

## Meeting URL for humans

Individual meeting pages live at:
- `/Portal/MeetingInformation.aspx?Org=Cal&Id={meeting_id}`

## Migration impact on the codebase

- Deleted `src/ccs/boarddocs.py`, replaced with `src/ccs/diligent.py`.
- `config.py`: added `DILIGENT_BASE`, removed `BOARDDOCS_*`, changed `Body`
  from `title_patterns` to `type_id`, added `BODIES_BY_TYPE_ID` and
  `body_for_type_id()` — since replaced by `body_for_meeting()`, which reads
  the title again as a tiebreaker (see above).
- `summarize.py`: `ingest_boarddocs` → `ingest_diligent`,
  `summarize_boarddocs_lookahead` → `summarize_diligent_lookahead`. Prompt
  now consumes the agenda HTML as a text blob rather than assembling from
  fielded item detail.
- `report.py`, `general.py`, `cli.py`: swapped imports; `ccs ingest` now
  takes `diligent:<numeric_id>` instead of `boarddocs:<unique>`.
- Manifest IDs: new prefixes are `diligent:`, `diligent-preview:`,
  `diligent-cancelled:`. Old `boarddocs:*` entries (if any) become inert —
  they don't collide with new runs.

## Verified on Aug 17, 2026

- `ccs check --since 2026-07-01 --until 2026-09-15` → 6 of 11 tracked
  bodies have records (Board, both COTWs, Board of Health, BCCD, SWCD).
- `ccs ingest diligent:1622` (July 16, 2026 Board Meeting) ran end-to-end:
  agenda pulled, YouTube video matched, transcript extracted, summary
  written (~$0.08 on Sonnet 4.5). Output captured real detail (courthouse
  door change order, advisory ballot questions, bridge contracts).
