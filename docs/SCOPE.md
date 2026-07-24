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
| Municipalities (Belvidere, Poplar Grove, etc.) | `excluded` | City-level, not county. |
| School districts | `excluded` | Independent. |
