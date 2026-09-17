# city-county-summarizer (`ccs`)

Personal CLI that watches local government activity in **Boone County, IL**
across five separate governments and 22 bodies:

| Government | Bodies tracked |
|---|---|
| Boone County | County Board, two Committees of the Whole, and appointed sub-bodies (Zoning, Planning, Health, Ag Easement, LEPC, Veterans) |
| City of Belvidere | City Council, Committee of the Whole, Planning & Zoning, Historic Preservation, Fire & Police Commission |
| Belvidere CUSD 100 | Board of Education and its four committees |
| Belvidere Township Park District | Board of Commissioners |
| The two conservation districts | BCCD and Soil & Water, each an independent elected board |

It publishes **[The Belvidere Wire](https://belviderewire.com/)**
— *a first draft of the public record*. A static site with one page per body
listing everything filed from it, one page per meeting carrying its full
summary, and a reference page per government covering how it works, who
currently serves, and when its bodies meet. Published to GitHub Pages; body and
meeting pages are regenerated from the manifest by `ccs build-site`, reference
pages by `ccs summary`.

The site is framed as a publication, and its copy uses newsroom words for
things the code names literally. The mapping is worth knowing before you edit
either side:

| On the site | In the code |
|---|---|
| beat | a tracked `Body` (`_bodies/`, `body_id`) |
| dispatch | a meeting page (`_meetings/`, a `MeetingRecord`) |
| the lede | the `## The lede` section each summary prompt asks for |
| backgrounder | a per-government About page under `website/about/` |
| the wire | the Atom feed at `/feed/meetings.xml` |
| the byline | the disclosure block in `_layouts/meeting.html` |

Identifiers were deliberately left alone — only reader-facing copy carries the
publication vocabulary. The masthead's own explanation of how dispatches are
written lives at
[/method/](https://belviderewire.com/method/),
which is generated from `website/method.md` and is the one page to update when
the prompts or the sources change.

Materials come from two Diligent Community portals (the county's and the school
district's), four WordPress sites, and YouTube auto-captions where a meeting is
streamed. Scanned PDFs are OCR'd. Dispatches are written by Claude Sonnet 4.5,
and every one of them carries a byline saying so.

## Prerequisites

- Python 3.9+ (developed on 3.9; type annotations use `from __future__ import annotations`)
- An Anthropic API key — get one at <https://console.anthropic.com/>
- `ocrmypdf` (optional, `brew install ocrmypdf`) — only needed for sources
  that post scanned PDFs. Without it those meetings summarize from whatever
  text is extractable.

## Install

```bash
git clone https://github.com/michaeldhart/city-county-summarizer
cd city-county-summarizer
python3 -m pip install --user -e .
cp .env.example .env      # then paste your key
```

The install registers a `ccs` script at `~/.local/bin` (or
`~/Library/Python/3.X/bin` on macOS). If that directory isn't on your PATH,
invoke as `python3 -m ccs.cli …` instead of plain `ccs`.

## Commands

### `ccs summary`

Rebuilds the backgrounder for each government under `website/about/`, plus the
`/about/` index. **`website/about.md` is generated, not hand-authored** —
`general.write_about_index()` rewrites it wholesale, so edit the copy there. Fetches that government's own public pages and, where the body
publishes to a Diligent portal, takes the current roster from its most recent
meeting record — more reliable than a web page, which lags reorganizations.
One Claude call per government.

```bash
ccs summary                 # all four
ccs summary belvidere       # just one
```

Cost: ~$0.10 per government, so ~$0.40 for a full rebuild.

### `ccs check`

Dry-run preview — no Claude calls. Prints an ASCII table of which tracked
bodies have any records in the given window. Useful to run before `ccs sync`
to see whether the run will produce anything worth paying for.

```bash
ccs check                                   # default window: last 35 days
ccs check --since 2026-04-01
```

Sample output:

```
+-----------------------------------------------+---------+
| Source                                        | Records |
+-----------------------------------------------+---------+
| Boone County Board                            | ✅       |
| Regional Planning Commission                  | ❌       |
| Board of Health                               | ✅       |
...
+-----------------------------------------------+---------+
```

Cost: free — hits only the meeting-list endpoints.

### `ccs sync`

Discovers meetings in the window and ingests any that aren't already in the
manifest — summarizing each with Claude and recording it. Run `ccs build-site`
afterward to publish newly-ingested meetings to the site.

```bash
ccs sync                                    # default window: last 35 days
ccs sync --since 2026-06-01
ccs sync --only d100 --since 2026-01-01     # one jurisdiction, source, or body
```

`--only` takes a comma-separated list of body ids, source names, or
jurisdiction ids. Without it, a wide `--since` backfills every tracked
government at once — which is rarely what you want, and never cheap.
`ccs check` accepts the same flag for a free preview.

Cost: ~$0.05–$0.15 per meeting summarized. A busy month with ~15 meetings
runs ~$1–$2. Meetings already ingested are reused from the manifest —
repeat runs are near-free.

### `ccs ingest <source:key>`

Force-ingest one specific meeting, ignoring the manifest.

```bash
ccs ingest diligent:1622            # numeric meeting id from the Diligent portal
ccs ingest d100:993                 # District 100's portal is a separate tenant
ccs ingest bpd:20260908             # PDF-index sources use the source's own key
ccs ingest bccd:20260420            # Boone County Conservation District, by date
ccs ingest swcd:20260701            # Soil & Water Conservation District, by date
```

Useful when you want to re-summarize after prompt tuning, or pull a meeting
outside the default sync window.

### `ccs backfill-resources`

Every dispatch carries a Resources column listing the raw materials
behind its summary — the Diligent meeting page, agenda and minutes PDFs,
the YouTube recording, and any documents linked from the agenda. It is
also what the page's byline is built from, so a record with an empty
column gets a vaguer byline. Records ingested before that column existed
have nothing to show; this fills them in. Free, no Claude calls: Diligent
meetings rebuild from the agenda HTML already cached on disk, and PDF
sources re-read their public index to recover the minutes link.

```bash
ccs backfill-resources
ccs backfill-resources --only belvidere
```

Only records with an empty list are touched, so it's safe to re-run. Some
meetings come back partly reconstructed — the park district and Belvidere
index pages only show a year or two, so anything older has dropped off the
public site and keeps just the one link already on record.

### `ccs brief`

Writes 1–3 **briefs** per meeting — short, headline-bearing items used to build
the front page — from that meeting's finished summary. One Claude call per
meeting; the dispatch itself is untouched.

```bash
ccs brief                                   # default window: last 35 days
ccs brief --since 2026-01-01                # the whole archive
ccs brief --only belvidere --force          # re-write even where unchanged
```

Briefs land in `data/meetings/<id>/briefs.json` beside the summary they were
written from, with a fingerprint of that summary. Re-runs skip meetings whose
summary hasn't changed, so running it over the whole archive is free except
where a summary was actually rewritten — which is also how a prompt change
picks up the meetings it affects.

Cost: ~$0.01 per meeting (the input is the summary, not the transcript). A full
174-meeting backfill is ~$2; a normal month is ~$0.15.

### `ccs front-page`

Ranks recent briefs and publishes a numbered **issue** — written to
`website/_front_pages/NNN.md` and copied to `website/index.md`.

```bash
ccs front-page                              # default: top 12 from the last 30 days
ccs front-page --window-days 45 --count 16
ccs front-page --no-rerank                  # deterministic order only, free
ccs front-page --list-briefs                # brief ids, for docs/PINS.md
ccs front-page --list                       # back issues, newest first
ccs front-page --publish 2                  # re-publish an old issue, no Claude call
```

Issue numbers are derived by scanning the directory, not from a counter, so a
bad edition is disposable: delete `_front_pages/003.md`, run again, and you get
a new No. 3 rather than a No. 4 with a hole behind it. Every issue stays
published at `/issues/NNN/` and is listed at
[`/issues/`](https://belviderewire.com/issues/) —
the issue number in the folio line links there.

Selection runs in three passes: a date window, a free deterministic sort (kind,
then score, then recency), then one Claude call that re-orders a shortlist
against each other — the judgment a per-meeting score can't make, since each
brief was written without knowing the others exist. `--no-rerank` stops after
pass two and costs nothing.

When the wire has been quiet the window widens in 15-day steps (up to 180) so
the page fills, and says so in the folio.

Pin a brief by adding its id to [`docs/PINS.md`](docs/PINS.md). A pinned brief
is always included, but keeps its ranked position — pinning holds something on
the page without inflating it.

Cost: ~$0.02 per run.

### `ccs build-site`

Regenerates `website/_bodies/` and `website/_meetings/` — the Jekyll
collections behind the published site — from the current manifest. One
page per tracked body (its beat page, listing every dispatch filed from
it) and one page per ingested meeting (the dispatch: its cached summary,
its byline, and its Resources column). Fully rewrites both collections
each run; free, no Claude calls.

```bash
ccs build-site
```

## Previewing the site locally

The site builds with the Ruby recorded in `website/.ruby-version` — the same
one CI uses. Search is a separate post-build step, so a plain `jekyll serve`
serves the site without it:

```bash
cd website
bundle exec jekyll build
npx -y pagefind@1.5.2 --site _site
bundle exec jekyll serve --skip-initial-build --no-watch
```

Then open <http://localhost:4000/>.

`--skip-initial-build` is what matters: without it `jekyll serve` regenerates
`_site` and deletes the `_site/pagefind/` index that was just built, and the
search page comes up empty. For ordinary content work where search does not
matter, plain `bundle exec jekyll serve` is fine.

## Configuring what's tracked

Edit [`docs/SCOPE.md`](docs/SCOPE.md) — every governmental body has a status:

- `tracked` — ingested per-meeting and published to the site.
- `mentioned` — appears in the general summary but not ingested per-meeting.
- `excluded` — ignored entirely.

The app parses `SCOPE.md` at runtime. Change a status, save, and the next
run picks it up. No config files elsewhere.

## Outputs and layout

```
data/                           # gitignored — regenerable cache
  manifest.json                 #   record of what's been ingested
  meetings/<id>/
    summary.md                  #   per-meeting summary
    agenda.html, items.json     #   raw BoardDocs materials
    transcript.txt, video.en.vtt  # YouTube captions when available
    agenda.pdf, minutes.pdf     #   CD/SWCD PDFs when applicable
docs/
  SCOPE.md                      # tracked bodies (edit to re-scope)
  SOURCES.md                    # every URL the app pulls from
  PLAN.md                       # architecture notes
  SPIKE_NOTES.md                # findings from the v1 spike (BoardDocs era)
  DILIGENT_MIGRATION.md         # findings from the Aug 2026 Diligent migration
website/                        # Jekyll site published to GitHub Pages
  index.md                       #   front page; GENERATED by `ccs front-page`
  _front_pages/NNN.md            #   back issues; one per `ccs front-page` run
                                 #   (frozen markup — a layout change affects only newer issues)
  issues.md                      #   the back-issue archive listing
  beats.md                       #   every tracked body, grouped by government
  method.md                      #   how dispatches are written; hand-authored
  about.md                       #   backgrounder index; NOT hand-editable — see `ccs summary`
  _bodies/<id>.md                #   one per tracked body; regenerated by `ccs build-site`
  _meetings/<record-id>.md       #   one per ingested meeting; regenerated by `ccs build-site`
src/ccs/                        # the package
```

## What Claude sees for a meeting

For a **County Board or COTW meeting**:
- Meeting metadata (name, date, location, time, member roster)
- Full agenda as text (rendered from the Diligent HTML)
- Full YouTube auto-caption transcript (~13k words for a 90-min meeting)

For a **sub-body meeting** (Zoning, Planning, Health, Ag Easement):
- Same Diligent materials as above
- No transcript — sub-body meetings aren't recorded

For a **Conservation District meeting** (BCCD, SWCD):
- Agenda PDF text (via `pdfplumber`)
- Minutes PDF text when the previous meeting's minutes are published

### How the YouTube transcript flows into a summary

The transcript is only ever raw material for the Claude prompt — it never
appears verbatim in the summary. The cleaned transcript is spliced into the
prompt alongside the agenda text, and Claude draws on it mainly for
**Attendance & housekeeping**, **Decisions & votes**, **Discussion items**,
**Public comment**, and **Notable moments** (see
`summarize._build_diligent_prompt`).

The full transcript is saved to `data/meetings/<id>/transcript.txt` for
reference, and each manifest record tracks `video_id` and `has_transcript`,
but neither the transcript text nor a video link is currently rendered into
the site — only Claude's summary is.

## Limitations worth knowing

- **Agendas aren't always published in advance.** The county sometimes
  doesn't post an agenda to Diligent until close to (or right after) the
  meeting. If a meeting is on YouTube but missing after a sync, wait a
  few days and re-run.
- **LEPC and Veteran's Assistance aren't on Diligent.** Those bodies stay
  in the tracked list but never produce records. If we find where they
  publish, we'll add a scraper.
- **Sub-body meetings have no video.** Only Board and the two COTWs are
  streamed. Sub-body summaries work off the agenda only.
- **Auto-caption typos.** YouTube's auto-captions get most of it right but
  garble proper nouns; Claude corrects the obvious ones. Numbers and dollar
  amounts come through cleanly.
- **Scanned PDFs need OCR.** Documents thinner than 150 chars/page are
  routed through `ocrmypdf`, which caches a searchable `*.ocr.pdf` beside
  the original. Without that binary installed the run warns and summarizes
  from whatever text it could extract.
- **The manifest is authoritative for "did we ingest this?"** — deleting
  `data/manifest.json` forces the next `ccs sync` to re-ingest everything
  in the window (and re-spend on Claude).

## Extending it

- To watch a new body on an existing source: add a `Body` entry in
  [`src/ccs/config.py`](src/ccs/config.py), add it to `SCOPE.md`, set
  status to `tracked`.
- To add a whole new government: add a `Jurisdiction` (it owns the YouTube
  channel, if any), then register its source in
  [`src/ccs/sources.py`](src/ccs/sources.py) — `DiligentSource(base_url)`
  for a Diligent tenant, or `PdfIndexSource(lister)` for a site that posts
  agenda/minutes PDFs.
- To try a different summarization model: change `CLAUDE_MODEL` in
  [`src/ccs/config.py`](src/ccs/config.py).
- To retune prompts: `summarize._build_diligent_prompt`,
  `summarize._build_pdf_meeting_prompt`, and `general._build_prompt`.

For deeper background, [`docs/SPIKE_NOTES.md`](docs/SPIKE_NOTES.md) has the
end-to-end validation notes from the initial build, including the
non-obvious bits (BoardDocs endpoint quirks, yt-dlp player-client workaround,
the "minutes live on the next meeting's agenda" pattern).

## Licensing

Two different things live in this repository, and they are licensed
differently.

**The software** — `src/`, `website/_layouts/`, `website/_includes/`,
`website/assets/`, `.github/` — is licensed under the
[Apache License 2.0](LICENSE). Use it, fork it, run it for your own county.
Keep the copyright and license notice, say so in files you modify (section
4(b)), and carry [`NOTICE`](NOTICE) into derivative works (section 4(d)).

**The published content** — everything generated under `website/_meetings/`,
`website/_bodies/`, `website/_front_pages/` and `website/about/` — is not
covered by that license and carries no copyright claim. It is written by a
machine from public records, with no human author, so there is nothing here to
reserve. Reuse it freely; a credit to The Belvidere Wire is appreciated and not
required.

Note what neither of those reaches: running this pipeline and publishing the
site it produces is not distributing the software, so nothing obliges a fork to
publish its changes or to credit this project. If you build something on it,
consider doing both anyway.

"The Belvidere Wire" is the publication's name, not part of the grant — the
Apache License explicitly conveys no trademark rights (section 6). A site built
from this code should publish under its own masthead.
