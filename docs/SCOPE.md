# Scope

Governmental bodies the app tracks. Each entry has a status:

- **`tracked`** — included in monthly reports (recap + lookahead). Counted in the general summary.
- **`mentioned`** — named in the general summary for context, but no meeting ingestion.
- **`excluded`** — not covered at all.

Change the status on any line to re-scope. The app reads this file at runtime.

## County Board

| Body | Status | Notes |
|------|--------|-------|
| Boone County Board (12 members, 3 districts) | `tracked` | Primary legislative body. |
| COTW – Administrative & Legislative | `tracked` | Committee of the Whole. |
| COTW – Finance, Taxation & Salaries | `tracked` | Committee of the Whole. |

## County boards & commissions (appointed by the Board)

| Body | Status | Notes |
|------|--------|-------|
| Regional Planning Commission | `tracked` | On BoardDocs. |
| Zoning Board of Appeals | `tracked` | On BoardDocs. |
| Agricultural Conservation Easement & Farmland Protection Commission | `tracked` | On BoardDocs. |
| Board of Health | `tracked` | Meets at Health Dept, noon. On BoardDocs. |
| Local Emergency Planning Committee (LEPC) | `tracked` | Listed on county departments page. |
| Veteran's Assistance Commission | `tracked` | Listed on county departments page. |

## Departments (mentioned, not tracked as meeting bodies)

Listed in the general summary so questions like "who's the coroner?" are answerable. No agenda ingestion.

- 17th Judicial Circuit Court
- Administration
- Animal Services
- Assessment Office
- Building & Zoning
- Clerk & Recorder
- Clerk of the Circuit Court
- Coroner
- Corrections & County Jail
- Emergency Management
- Geographic Information Systems & Maps
- Health Department
- Highway Department
- Planning Department
- Probation
- Public Defender
- Sheriff's Office
- State's Attorney
- Storm Water and Pollution Control
- Treasurer

## Separate governmental bodies (not the county board — excluded by default)

These exist in Boone County but are governed independently. Flip to `tracked` if you want them.

| Body | Status | Notes |
|------|--------|-------|
| Boone County Conservation District | `tracked` | Separate elected board. Own site: bccdil.org. |
| Boone County Soil & Water Conservation District | `tracked` | Separate body. Own site: boonecountyswcd.org. |
| Municipalities (Belvidere, Poplar Grove, etc.) | `excluded` | City-level. Belvidere itself is tracked below. |
| School districts | `excluded` | Independent. BCUSD 100 is tracked below; no other district is. |

## Belvidere Township Park District

Independently elected five-member Board of Commissioners covering Belvidere
Township, including land outside the city limits. Formed by referendum in 1919.
Agendas and minutes at belviderepark.org; no meeting video is published.

The board does all its business itself — there are no standing committees. The
Parks & Conservation Foundation is a separate 501(c)(3) and publishes nothing.

| Body | Status | Notes |
|------|--------|-------|
| Belvidere Township Park District Board | `tracked` | 2nd Tuesday, 5:00 PM, Baltic Mill Annex. Occasional 4th-Tuesday and special meetings. |

## Belvidere Community Unit School District 100

Independently elected seven-member Board of Education covering Boone, McHenry and
DeKalb counties. Publishes to its own Diligent Community tenant
(`district100.community.highbond.com`) — the same platform the county uses.

Workshops, retreats, town halls, hearings and special meetings are filed as separate
Diligent meeting types but are all the Board of Education meeting under a different
label, so they roll up into the Board's page rather than getting pages of their own.

| Body | Status | Notes |
|------|--------|-------|
| BCUSD 100 Board of Education | `tracked` | 3rd Monday, 6:00 PM, 1201 5th Ave. Includes specials, workshops, retreats, town halls, hearings. |
| BCUSD 100 Business Services Committee | `tracked` | Roughly monthly, 4:00 PM. |
| BCUSD 100 Educational Services Committee | `tracked` | Roughly monthly, 4:00 PM. |
| BCUSD 100 Policy & Personnel Committee | `tracked` | Roughly monthly, 4:30 PM. |
| BCUSD 100 Parent Teacher Advisory Committee | `tracked` | Intermittent. |

Not tracked: the `Main Governing Board - Archive` meeting type (560 pre-March-2025
meetings imported from BoardDocs). It lumps every body type under one id and would
need title-parsing to attribute correctly — out of scope while the window is 2026.
