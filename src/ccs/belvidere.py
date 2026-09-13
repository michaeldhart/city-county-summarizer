"""City of Belvidere — scraper for the WordPress/Elementor document archive.

One site serves five bodies. Each has a hub page listing one link per year;
each year page is a flat <ul> of li.elementor-icon-list-item entries whose
text carries the meeting date. There is no API — the Events Manager REST
route returns 401 and its iCal feed is hard-capped at 50 events.

Three things make this messier than the other PDF-index sources:

- Every year page also lists three site-wide sidebar PDFs (a HIPAA notice, an
  ash borer fact sheet, sidewalk specs) through the same selector. Requiring a
  parseable date filters them out.
- Link text varies by body. Council and COW share one agenda hub and are told
  apart by name; Council minutes are a bare date with no body or keyword, so
  the hub supplies both; Fire & Police puts the date first rather than last.
- Year-page slugs are unpredictable (`-2` suffixes, a literal "amp", singular
  and plural drift), so they're discovered by crawling the hub, never built.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import HTTP_HEADERS

BASE = "https://www.belvidereil.gov"

# Be polite: the origin is slow (wp-before-template ~870ms) and this crawls
# two pages per body per run.
_DELAY_SECONDS = 0.3

_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),?\s+(20\d{2})\b",
    re.IGNORECASE,
)
_CANCELLED_RE = re.compile(r"cancell?ed|reschedul", re.IGNORECASE)
_YEAR_LINK_RE = re.compile(r"^\s*(20\d{2})\s*$")


@dataclass(frozen=True)
class _Hub:
    url: str
    body_id: str        # body this hub belongs to, unless the text says otherwise
    kind: str           # document kind when the link text doesn't say


_HUBS = (
    _Hub(f"{BASE}/past-agendas/", "belvidere-council", "agenda"),
    _Hub(f"{BASE}/city-council-minutes/", "belvidere-council", "minutes"),
    _Hub(f"{BASE}/planning-zoning-commission/", "belvidere-pzc", "agenda"),
    _Hub(f"{BASE}/historic-preservation-committee/", "belvidere-hpc", "agenda"),
    _Hub(f"{BASE}/fire-police-commission/", "belvidere-fpc", "agenda"),
)

# Only the combined Council/COW agenda hub actually mixes bodies, but a body
# named in the text always wins over the hub's default.
_BODY_HINTS = (
    (re.compile(r"committee of the whole", re.I), "belvidere-cow"),
    (re.compile(r"city council", re.I), "belvidere-council"),
    (re.compile(r"planning\s*&?\s*zoning|\bPZC\b", re.I), "belvidere-pzc"),
    (re.compile(r"historic preservation|\bHPC\b", re.I), "belvidere-hpc"),
    (re.compile(r"fire\s*&?\s*police", re.I), "belvidere-fpc"),
)

_BODY_SLUGS = {
    "belvidere-council": "council",
    "belvidere-cow": "cow",
    "belvidere-pzc": "pzc",
    "belvidere-hpc": "hpc",
    "belvidere-fpc": "fpc",
}


@dataclass(frozen=True)
class BelvidereMeeting:
    date: date
    body_id: str
    agenda_url: Optional[str]
    minutes_url: Optional[str]

    @property
    def key(self) -> str:
        """Body-qualified: Council and COW can meet on the same date (Apr 20, 2026)."""
        return f"{_BODY_SLUGS[self.body_id]}-{self.date.strftime('%Y%m%d')}"

    @property
    def name(self) -> str:
        return ""   # the body's display name is the meeting's name here


def list_meetings(min_year: Optional[int] = None) -> list[BelvidereMeeting]:
    """Every meeting with at least one document, newest first.

    Defaults to the current year and the one before it. The full archive runs
    to 2014 across ~50 year pages; the manifest is the durable copy, so there's
    no reason to re-crawl a decade on every sync.
    """
    if min_year is None:
        min_year = date.today().year - 1

    docs: dict = {}
    for hub in _HUBS:
        for year_url in _year_pages(hub.url, min_year):
            for body_id, meeting_date, kind, url in _parse_year_page(year_url, hub):
                slot = docs.setdefault((body_id, meeting_date), {"agenda": None, "minutes": None})
                if slot[kind] is None:
                    slot[kind] = url

    out = [
        BelvidereMeeting(
            date=meeting_date,
            body_id=body_id,
            agenda_url=slot["agenda"],
            minutes_url=slot["minutes"],
        )
        for (body_id, meeting_date), slot in docs.items()
        if slot["agenda"] or slot["minutes"]
    ]
    out.sort(key=lambda m: (m.date, m.body_id), reverse=True)
    return out


def _get(url: str) -> str:
    time.sleep(_DELAY_SECONDS)
    r = requests.get(url, headers=HTTP_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def _year_pages(hub_url: str, min_year: int) -> list[str]:
    """Year links on a hub, filtered to min_year and later.

    The link text is the bare year; the slug is not derivable from it.
    """
    soup = BeautifulSoup(_get(hub_url), "html.parser")
    seen: set = set()
    out: list = []
    for a in soup.find_all("a", href=True):
        m = _YEAR_LINK_RE.match(a.get_text(" ", strip=True))
        if not m or int(m.group(1)) < min_year:
            continue
        href = a["href"].strip()
        if href.startswith("/"):
            href = BASE + href
        if not href.startswith(BASE) or href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out


def _parse_year_page(url: str, hub: _Hub) -> list:
    soup = BeautifulSoup(_get(url), "html.parser")
    out: list = []
    for li in soup.select("li.elementor-icon-list-item"):
        label = li.select_one("span.elementor-icon-list-text")
        a = li.find("a", href=True)
        if label is None or a is None:
            continue
        text = re.sub(r"\s+", " ", label.get_text(" ", strip=True)).strip()
        meeting_date = _parse_date(text)
        if meeting_date is None:
            continue          # sidebar boilerplate — no date, not a meeting doc
        if _CANCELLED_RE.search(text):
            continue
        href = _clean_href(a["href"])
        if href is None:
            continue
        out.append((_body_for(text, hub), meeting_date, _kind_for(text, hub), href))
    return out


def _body_for(text: str, hub: _Hub) -> str:
    for pattern, body_id in _BODY_HINTS:
        if pattern.search(text):
            return body_id
    return hub.body_id


def _kind_for(text: str, hub: _Hub) -> str:
    if re.search(r"minutes", text, re.IGNORECASE):
        return "minutes"
    if re.search(r"agenda|packet", text, re.IGNORECASE):
        return "agenda"
    return hub.kind


def _clean_href(href: str) -> Optional[str]:
    """One link in the wild is a doubled-up URL (`https://www.https://www...`),
    so validate rather than trusting the markup."""
    href = href.strip()
    if href.startswith("/"):
        href = BASE + href
    if href.count("://") != 1 or not href.startswith("http"):
        return None
    return href


def _parse_date(text: str) -> Optional[date]:
    """Date can lead or trail the body name, so search rather than anchor."""
    m = _DATE_RE.search(text)
    if m is None:
        return None
    try:
        return datetime.strptime(
            f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y"
        ).date()
    except ValueError:
        return None
