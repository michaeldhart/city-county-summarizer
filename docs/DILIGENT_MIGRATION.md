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

Type 17 ("Imported Meetings: 2011-2025") is a lump for historical data
migrated in bulk from the old system.

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
  `body_for_type_id()`.
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
