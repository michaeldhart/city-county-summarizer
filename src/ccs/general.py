"""About-page generator — one living source-of-truth doc per government.

Each spec names the public pages to pull, an outline for the document, and
optionally a Diligent body whose latest meeting supplies the current roster
(more reliable than a web page, which lags the annual reorganization).

The two conservation districts are covered inside the county's page rather
than getting their own — see config.ABOUT_PAGE_FOR.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import anthropic
import requests
from bs4 import BeautifulSoup

from . import diligent, sources
from .config import (
    ABOUT_PAGE_FOR,
    BODIES_BY_ID,
    CLAUDE_MODEL,
    DOCS_DIR,
    HTTP_HEADERS,
    JURISDICTIONS_BY_ID,
    REPO_ROOT,
    load_env,
)

ABOUT_DIR = REPO_ROOT / "website" / "about"


@dataclass(frozen=True)
class SummarySpec:
    jurisdiction_id: str
    roster_body_id: Optional[str]
    sources: dict
    outline: str
    intro: str = ""


_BOONE_OUTLINE = """## Overview
(2-3 paragraphs: what Boone County is - geography, seat, size - and how its government is organized.)

## The County Board
- Composition (member count, districts)
- How chair / vice-chair are selected and their terms
- Meeting schedule and location
- The Committee of the Whole model - how it works, when it's used

## Current members
(Table or list - name, role/title, district if known. Use the Diligent roster as
the authoritative current roster; supplement with anything from the county site.)

## Standing committees (COTWs)
- Administrative & Legislative - purpose, cadence
- Finance, Taxation & Salaries - purpose, cadence

## Boards, commissions, and committees
(Each body tracked in SCOPE.md under the county: name, purpose, membership, cadence.)

## The conservation districts
(Boone County Conservation District and Boone County Soil & Water Conservation
District - independent bodies with their own elected boards, tracked here. Give
each its own sub-section, headed with the district's full name - /beats/ links
straight to those headings.)

## Departments
(Directory. Where a source names a head or elected official, include them.)

## Key elected and appointed officials
(Short who's-who - Clerk, Sheriff, State's Attorney, Coroner, Treasurer, Circuit Clerk.)

## Meeting cadence at a glance
(One compact table: body -> typical day/time/location.)

## Where to find more
(Primary sources, plus 55 ILCS 5 for statutory context.)"""

_BELVIDERE_OUTLINE = """## Overview
(2-3 paragraphs: what Belvidere is - location, population, character - and its form of government.)

## Form of government
- Mayor-council, aldermanic. Ward count and how many aldermen per ward.
- Terms and how seats are staggered.
- Who the mayor, clerk and treasurer are, with term end dates if stated.

## The City Council
- Composition and meeting schedule/location
- What the Committee of the Whole is and how it divides its subject areas
- Note explicitly: the Committee of the Whole publishes agendas and packets but
  not minutes, so its video recording is the only record of discussion.

## Current aldermen
(Table by ward - ward number, both aldermen.)

## Boards and commissions
(For each: purpose, cadence, and whether it publishes agendas/minutes. Note that
the Planning & Zoning Commission also sits as the Zoning Board of Appeals, so
there is no separate ZBA. List the bodies that publish nothing - the two pension
boards, library board, council on aging, community building complex, and the
foreign fire insurance fund - as existing but untracked.)

## Departments and staff
(Department directory with named directors where the source gives them.)

## Meeting cadence at a glance
(One compact table: body -> typical day/time/location.)

## Where to find more
(Primary sources, plus the municipal code on Municode and 65 ILCS 5 for statutory context.)"""

_D100_OUTLINE = """## Overview
(2-3 paragraphs: what the district covers, its size, and how a unit school district is governed.)

## The Board of Education
- Member count, how members are elected, term length, whether the seats are paid
- Residency rules across townships if the sources state them
- Meeting schedule and location

## Current members
(Table - name and office. The roster below is authoritative for membership. The
district's own board page is JavaScript-rendered and does not reach this prompt,
so office titles are usually unavailable - say so once rather than repeating
"Not in sources" down a whole column.)

## Committees
(Business Services, Educational Services, Policy & Personnel, Parent Teacher
Advisory - purpose and cadence for each.)

## Administration
(Superintendent and cabinet-level roles named in the sources.)

## Schools
(List the schools with grade levels. Include enrollment if a source gives it.)

## Meeting cadence at a glance
(One compact table: body -> typical day/time/location.)

## Where to find more
(Primary sources, plus 105 ILCS 5 for statutory context.)"""

_BPD_OUTLINE = """## Overview
(2-3 paragraphs: what the district is, when it formed, what area it covers.)

## The Board of Commissioners
- Member count, election, term length, whether the role is paid
- Meeting schedule and location
- Note that the board has no standing committees and conducts business as a whole

## Current commissioners
(Table - name and office where stated.)

## Leadership
(Executive Director and senior staff named in the sources.)

## Facilities and programs
(Parks, recreation centre, ice arena, aquatics, trails, special recreation, and
the before/after-school programs. Do not invent facilities not in the sources.)

## Finances
(Tax levy and budget figures where a source states them, with the year.)

## The Parks & Conservation Foundation
(Separate 501(c)(3) - what it is and how it relates to the district.)

## Where to find more
(Primary sources, plus 70 ILCS 1205 for statutory context.)"""


SPECS: tuple = (
    SummarySpec(
        jurisdiction_id="boone-county",
        roster_body_id="board",
        outline=_BOONE_OUTLINE,
        intro="the county board, its committees and appointed bodies, and the "
              "two independent conservation districts",
        sources={
            "County Board (site)":
                "https://www.boonecountyil.gov/government/county_board/index.php",
            "County Board Members":
                "https://www.boonecountyil.gov/government/county_board_members.php",
            "County Board Duties":
                "https://www.boonecountyil.gov/government/county_board/county_board_duties.php",
            "Departments index":
                "https://www.boonecountyil.gov/government/departments/index.php",
            "Clerk & Recorder":
                "https://www.boonecountyil.gov/government/departments/clerk___recorder/index.php",
            "Planning Dept - boards & commissions":
                "https://www.boonecountyil.gov/government/departments/planning_department/commissions_boards_and_committees.php",
            "Board of Health":
                "https://www.boonecountyil.gov/government/departments/health_department/board_of_health.php",
            "Boone County Conservation District":
                "https://www.bccdil.org/about/",
            "BCCD board meetings":
                "https://www.bccdil.org/board-meetings/",
            "Soil & Water Conservation District":
                "https://boonecountyswcd.org/",
            "Wikipedia - Boone County, IL":
                "https://en.wikipedia.org/wiki/Boone_County,_Illinois",
            "Ballotpedia - Boone County, IL":
                "https://ballotpedia.org/Boone_County,_Illinois",
        },
    ),
    SummarySpec(
        jurisdiction_id="belvidere",
        roster_body_id=None,
        outline=_BELVIDERE_OUTLINE,
        intro="the City Council, the Committee of the Whole, and the city's "
              "boards and commissions",
        sources={
            "Aldermen": "https://www.belvidereil.gov/aldermen/",
            "Mayor": "https://www.belvidereil.gov/mayor/",
            "City Clerk": "https://www.belvidereil.gov/city-clerk/",
            "Staff directory": "https://www.belvidereil.gov/staff-directory/",
            "Boards & commissions": "https://www.belvidereil.gov/boards-commissions/",
            "Council meetings": "https://www.belvidereil.gov/city-council-meetings/",
            "About Belvidere": "https://www.belvidereil.gov/about-us/",
            "Citizens' guide": "https://www.belvidereil.gov/citizens-guide/",
            "Wikipedia - Belvidere, IL": "https://en.wikipedia.org/wiki/Belvidere,_Illinois",
        },
    ),
    SummarySpec(
        jurisdiction_id="d100",
        roster_body_id="d100-board",
        outline=_D100_OUTLINE,
        intro="the Board of Education and its standing committees",
        sources={
            "Board of Education": "https://www.district100.com/boardofeducation",
            "About the Board": "https://www.district100.com/boardofeducation/abouttheboard",
            "Board meetings": "https://www.district100.com/boardofeducation/meetings",
            "Superintendent": "https://www.district100.com/about-d100/about-the-superintendent",
            "Schools": "https://www.district100.com/schools",
        },
    ),
    SummarySpec(
        jurisdiction_id="bpd",
        roster_body_id=None,
        outline=_BPD_OUTLINE,
        intro="the elected Board of Commissioners",
        sources={
            "About the district": "https://www.belviderepark.org/about-us/",
            "Board of Commissioners": "https://www.belviderepark.org/about-us/board/",
            "History": "https://www.belviderepark.org/about-us/history/",
            "Staff listing": "https://www.belviderepark.org/staff-listing/",
            "Financial information": "https://www.belviderepark.org/about-us/financial-information/",
        },
    ),
)

SPECS_BY_ID: dict = {s.jurisdiction_id: s for s in SPECS}


def build_about_page(jurisdiction_id: str) -> Path:
    """Regenerate one government's backgrounder. One Claude call."""
    load_env()
    spec = SPECS_BY_ID[jurisdiction_id]
    name = JURISDICTIONS_BY_ID[jurisdiction_id].display_name

    print(f"[{jurisdiction_id}] fetching sources...")
    source_texts = _fetch_sources(spec.sources)

    roster_text = ""
    if spec.roster_body_id:
        print(f"[{jurisdiction_id}] fetching roster from the latest meeting record...")
        roster_text = _diligent_roster(spec.roster_body_id)

    scope_md = (DOCS_DIR / "SCOPE.md").read_text()
    prompt = _build_prompt(name, spec, source_texts, roster_text, scope_md)
    print(f"[{jurisdiction_id}] prompt {len(prompt)} chars; calling Claude...")
    summary = _pin_standfirst(_pin_anchors(jurisdiction_id, _call_claude(prompt)))

    ABOUT_DIR.mkdir(parents=True, exist_ok=True)
    out = ABOUT_DIR / f"{jurisdiction_id}.md"
    out.write_text(_front_matter(name, jurisdiction_id) + summary)
    return out


# Rendered into every backgrounder under its title. Three jobs, in order: say a
# machine wrote it, date it, and point at the page that explains both. The
# dispatches have carried that disclosure since the first one was filed; these
# pages never had it, and they are the ones most easily mistaken for something
# a government published itself — they list officeholders, meeting times and
# phone numbers.
_STANDFIRST = (
    "Written by a machine from this government's own published pages, and "
    "current as of {when}. Rosters and meeting times change; where this and "
    "the government's own site disagree, theirs is right. "
    "[How this is written]({{{{ '/method/' | relative_url }}}})\n"
    "{{: .fine-print }}"
)


def _pin_standfirst(markdown: str, when: date | None = None) -> str:
    """Put the standfirst under the title, replacing whatever is in that slot.

    Written here rather than asked for in the outline because a model handed a
    date can echo it wrong, and because this is the one line on the page that
    has to be there — a reader who takes a backgrounder for the government's
    own material has been misled by omission.
    """
    when = when or date.today()
    line = _STANDFIRST.format(when=when.strftime("%B %-d, %Y"))

    # Anything already sitting between the title and the first section is the
    # old "_Generated ... by `ccs summary`_" stamp, or a previous standfirst.
    # subn, not comparing the result: re-running on a page that already carries
    # an identical standfirst substitutes successfully and changes nothing, and
    # equality would read that as a failure.
    body, hits = re.subn(r"\A\s*(# .*\n)(?:(?!^#{2,} ).*\n)*?(?=^#{2,} )",
                         r"\1\n" + line.replace("\\", "\\\\") + "\n\n",
                         markdown, count=1, flags=re.MULTILINE)
    if not hits:
        print("  WARNING: could not place the standfirst — no title followed by "
              "a section heading. The page will carry no disclosure.")
    return body


def _pin_anchors(jurisdiction_id: str, markdown: str) -> str:
    """Attach a stable anchor to the heading of each government folded into this page.

    The two conservation districts have no backgrounder of their own; they are
    sub-sections of the county's (see config.ABOUT_PAGE_FOR), and /beats/ links
    each district straight to its section. That link needs an id that does not
    move, and neither of the obvious sources gives one: kramdown derives its
    auto-id from the heading text, which a rewrite changes, and Liquid's
    slugify cannot reproduce kramdown's id for a heading containing "&"
    anyway.

    So the id is written here rather than asked for in the outline. The model
    writes prose; a piece of markup another page depends on is not its job to
    remember. Where the heading itself has gone missing there is nothing to
    attach to — that case warns rather than failing, because /beats/ falls back
    to linking the top of this page and the document is still correct, just
    less precisely linkable.
    """
    folded = sorted(jid for jid, host in ABOUT_PAGE_FOR.items()
                    if host == jurisdiction_id)
    for jid in folded:
        ial = "{: #%s }" % jid
        if ial in markdown:
            continue
        name = JURISDICTIONS_BY_ID[jid].display_name
        heading = re.compile(r"^(\#{2,4}[ \t]*%s[ \t]*)$" % re.escape(name),
                             re.MULTILINE)
        markdown, hits = heading.subn(r"\1\n" + ial, markdown, count=1)
        if not hits:
            print(f"  WARNING: no heading matching {name!r} in the "
                  f"{jurisdiction_id} backgrounder — /beats/ will link to the "
                  f"top of the page rather than #{jid}.")
    return markdown


def build_all() -> list:
    return [build_about_page(spec.jurisdiction_id) for spec in SPECS]


def write_about_index() -> Path:
    """Hand-written hub listing the per-government backgrounders. No Claude call.

    This rewrites website/about.md wholesale, so it is the only place the hub's
    copy can live — anything edited into the file by hand is lost on the next
    `ccs summary`. The links go through `relative_url` rather than being
    written out: a bare /about/<id>/ href hardcodes whatever baseurl happens to
    be configured. That is empty now the site serves from belviderewire.com,
    but it was /city-county-summarizer until the domain move, and a hardcoded
    path worked in local preview while 404ing in production.

    The page is no longer in the site nav — /beats/ links to each backgrounder
    directly — but the URL stays live and the four pages hang off it.
    """
    lines = [
        "---", "title: Backgrounders", "permalink: /about/", "---", "",
        "# Backgrounders", "",
        "A backgrounder is the reference material a reporter keeps beside them on a",
        "beat: how a government is organized, who currently serves, and when its",
        "bodies meet. There is one here for each government on the wire.", "",
    ]
    for spec in SPECS:
        name = JURISDICTIONS_BY_ID[spec.jurisdiction_id].display_name
        href = "{{ '/about/%s/' | relative_url }}" % spec.jurisdiction_id
        lines.append(f"- [{name}]({href}) - covers {spec.intro}.")
    lines += [
        "",
        "These are compiled from each government's own published sources and carry",
        "the date they were last rebuilt. For how the dispatches themselves are",
        "written, see [How this is written]({{ '/method/' | relative_url }}).",
        "",
    ]
    out = REPO_ROOT / "website" / "about.md"
    out.write_text("\n".join(lines))
    return out


def _front_matter(name: str, jurisdiction_id: str) -> str:
    return (
        "---\n"
        f'title: "Backgrounder: {name}"\n'
        f"permalink: /about/{jurisdiction_id}/\n"
        "---\n\n"
    )


def _fetch_sources(source_map: dict) -> dict:
    out: dict = {}
    for label, url in source_map.items():
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=20)
            r.raise_for_status()
            out[label] = _html_to_text(r.text)
            print(f"  {label}: {len(out[label])} chars")
        except Exception as e:
            out[label] = f"[Failed to fetch: {e}]"
            print(f"  {label}: FAILED ({e})")
    return out


def _diligent_roster(body_id: str) -> str:
    """Roster from the most recent past meeting of a Diligent body."""
    today = date.today()
    body = BODIES_BY_ID[body_id]
    base = sources.diligent_base(body.source)
    try:
        meetings = diligent.list_meetings(
            base, from_date=date(today.year - 1, 1, 1), to_date=today,
        )
    except Exception as e:
        return f"[Failed to list meetings: {e}]"
    past = [m for m in meetings if m.type_id in body.type_ids and m.date <= today]
    if not past:
        return f"[No recent {body.display_name} meeting found.]"
    past.sort(key=lambda m: m.date, reverse=True)
    latest = past[0]
    try:
        data = diligent.get_meeting_data(base, latest.id)
    except Exception as e:
        return f"[Failed to fetch meeting {latest.id}: {e}]"
    members = "\n".join(f"- {n}" for n in data.members) if data.members else "(none listed)"
    return (
        f"Source: {latest.date.isoformat()} meeting ({latest.title})\n"
        f"Location: {data.location}\nTime: {data.time}\nMembers:\n{members}"
    )


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return "\n".join(line for line in soup.get_text("\n").splitlines() if line.strip())


def _build_prompt(name: str, spec: SummarySpec, source_texts: dict,
                  roster_text: str, scope_md: str) -> str:
    sources_block = "\n\n".join(
        f"=== SOURCE: {label} ===\n{text}" for label, text in source_texts.items()
    )
    roster_block = (
        f"\n===== CURRENT ROSTER (from the body's latest meeting record) =====\n{roster_text}\n"
        if roster_text else ""
    )
    return f"""You are building a "living source of truth" document about {name}, in Boone County, Illinois.

This document has two audiences: (1) a human trying to learn how this government
works, and (2) an AI assistant that will reference it in future conversations.
Optimize for both: clear prose for the human, well-labeled facts for the AI.

Use only the sources provided below. Prefer the government's own site, and prefer
a roster taken from a meeting record over one taken from a web page - web rosters
lag reorganizations. Do not invent details.

Where sources disagree, say so explicitly rather than picking one silently. Where
a fact a reader would expect is missing, write "Not in sources" rather than
guessing or omitting the line — some of these sites render content with
JavaScript, so a fact being absent here does not mean the government hasn't
published it.

Produce a Markdown document with this structure:

# {name} - Backgrounder

{spec.outline}

Keep it factual and dense. Prefer bullet points over prose except in the Overview.

===== SCOPE (which bodies this project tracks, set by the user) =====
{scope_md}
{roster_block}
===== SOURCES =====
{sources_block}
"""


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    print(f"  usage: input={resp.usage.input_tokens} output={resp.usage.output_tokens}")
    return resp.content[0].text
