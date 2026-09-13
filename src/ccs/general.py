"""General summary generator — the living source-of-truth doc about Boone County government.

Pulls structural pages from the county site, the current board roster from the
most recent Board meeting on the Diligent portal, and one-time grounding from
Wikipedia. Synthesizes into the site's About page (`website/about.md`).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

from . import diligent, sources
from .config import (
    BODIES_BY_ID,
    CLAUDE_MODEL,
    DOCS_DIR,
    HTTP_HEADERS,
    REPO_ROOT,
    load_env,
)

OUTPUT_PATH = REPO_ROOT / "website" / "about.md"

_FRONT_MATTER = """---
title: About
permalink: /about/
---

"""

# Named for readability in the prompt; label appears above each source block.
_SOURCES: dict[str, str] = {
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
    "Planning Dept — boards & commissions":
        "https://www.boonecountyil.gov/government/departments/planning_department/commissions_boards_and_committees.php",
    "Board of Health":
        "https://www.boonecountyil.gov/government/departments/health_department/board_of_health.php",
    "Wikipedia — Boone County, IL":
        "https://en.wikipedia.org/wiki/Boone_County,_Illinois",
    "Ballotpedia — Boone County, IL":
        "https://ballotpedia.org/Boone_County,_Illinois",
}


def build_general_summary() -> Path:
    load_env()

    print("Fetching structural sources...")
    source_texts = _fetch_sources()

    print("Fetching current board roster from Diligent...")
    roster_text = _latest_board_roster()

    scope_md = (DOCS_DIR / "SCOPE.md").read_text()

    prompt = _build_prompt(source_texts, roster_text, scope_md)
    print(f"Prompt size: {len(prompt)} chars")

    print(f"Calling Claude ({CLAUDE_MODEL})...")
    summary = _call_claude(prompt)

    OUTPUT_PATH.write_text(_FRONT_MATTER + summary)
    return OUTPUT_PATH


def _fetch_sources() -> dict[str, str]:
    out: dict[str, str] = {}
    for label, url in _SOURCES.items():
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=20)
            r.raise_for_status()
            out[label] = _html_to_text(r.text)
            print(f"  {label}: {len(out[label])} chars")
        except Exception as e:
            out[label] = f"[Failed to fetch: {e}]"
            print(f"  {label}: FAILED ({e})")
    return out


def _latest_board_roster() -> str:
    """Pull the roster from the most recent past Board meeting on Diligent."""
    today = date.today()
    board_body = BODIES_BY_ID["board"]
    base = sources.diligent_base(board_body.source)
    try:
        meetings = diligent.list_meetings(
            base, from_date=date(today.year - 1, 1, 1), to_date=today,
        )
    except Exception as e:
        return f"[Failed to list Diligent meetings: {e}]"
    board = [m for m in meetings if m.type_id in board_body.type_ids and m.date <= today]
    if not board:
        return "[No recent Boone County Board meeting found on Diligent.]"
    board.sort(key=lambda m: m.date, reverse=True)
    latest = board[0]
    try:
        data = diligent.get_meeting_data(base, latest.id)
    except Exception as e:
        return f"[Failed to fetch meeting {latest.id}: {e}]"
    members = "\n".join(f"- {name}" for name in data.members) if data.members else "(no members listed)"
    return (
        f"Source: {latest.date.isoformat()} Board meeting ({latest.title})\n"
        f"Location: {data.location}\n"
        f"Time: {data.time}\n"
        f"Members:\n{members}"
    )


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return "\n".join(line for line in soup.get_text("\n").splitlines() if line.strip())


def _build_prompt(source_texts: dict[str, str], roster_text: str, scope_md: str) -> str:
    sources_block = "\n\n".join(
        f"=== SOURCE: {label} ===\n{text}"
        for label, text in source_texts.items()
    )
    return f"""You are building a "living source of truth" document about Boone County, IL government.

This document has two audiences: (1) a human trying to learn how the county works, and
(2) an AI assistant that will reference this document in future conversations. Optimize for both:
clear prose for the human, well-labeled facts for the AI.

Use only the sources provided below. If a fact appears in multiple sources, prefer the
county's own site or the current Board meeting roster (from Diligent) over Wikipedia/
Ballotpedia, which may be stale. Do not invent details.

Produce a Markdown document with this structure:

# Boone County, IL — Government Summary

_Generated {date.today().isoformat()} by `ccs summary`. Regenerate with the same command._

## Overview
(2–3 paragraphs: what Boone County is — geography, seat, size — and how its government is organized.)

## The County Board
- Composition (member count, districts)
- How chair / vice-chair are selected and their terms
- Meeting schedule and location
- The Committee of the Whole model — how it works, when it's used

## Current members
(Table or list — name, role/title, district if known. Use the Diligent Board meeting roster as
the authoritative current roster; supplement with anything from the county site.)

## Standing committees (COTWs)
- Administrative & Legislative — purpose, cadence
- Finance, Taxation & Salaries — purpose, cadence

## Boards, commissions, and committees
(For each body currently tracked in SCOPE.md as `tracked`: name, purpose, membership, meeting cadence.
Include the two Conservation Districts (BCCD, SWCD) noting they're independent bodies with elected boards.)

## Departments
(Directory of county departments. Where the source names a specific head or elected official, include them.)

## Key elected and appointed officials
(A short who's-who — Clerk, Sheriff, State's Attorney, Coroner, Treasurer, Circuit Clerk, etc.)

## Meeting cadence at a glance
(One compact table: body → typical meeting day/time/location.)

## Where to find more
(Links to the primary sources listed at the end, plus 55 ILCS 5 for statutory context.)

Keep it factual and dense. Prefer bullet points over prose except in the Overview.

===== SCOPE (statuses set by the user) =====
{scope_md}

===== CURRENT BOARD ROSTER (from Diligent Board meeting) =====
{roster_text}

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
