"""Belvidere Township Park District — scraper for /about-us/board/agendas-minutes/.

One <table> per year. The year appears *only* in the <h2> above each table —
the rows carry month and day but no year — so it has to be carried down.
Columns are Day | Meeting Name | Month | Date | Time | Location | Agenda |
Minutes, and agenda is told from minutes by column position: the link text is
always the literal word "Agenda" or "Minutes".

The page only ever shows two years; older meetings drop off as new ones are
added, so the manifest is the durable archive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from .config import HTTP_HEADERS

URL = "https://www.belviderepark.org/about-us/board/agendas-minutes/"

REGULAR_MEETING = "Regular Park Board"

_CANCELLED_RE = re.compile(r"cancell?ed|reschedul", re.IGNORECASE)


@dataclass(frozen=True)
class BpdMeeting:
    date: date
    name: str
    time: str
    agenda_url: str | None
    minutes_url: str | None

    @property
    def key(self) -> str:
        """Date alone isn't unique here — a Regular meeting and a Public Hearing
        can share both a date and a start time (Oct 28 and Nov 10, 2025), and a
        special meeting can share a date with the regular one (Aug 10, 2026)."""
        stamp = self.date.strftime("%Y%m%d")
        if self.name == REGULAR_MEETING:
            return stamp
        return f"{stamp}-{_slug(self.name)}"


def _fetch_html() -> str:
    r = requests.get(URL, headers=HTTP_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def list_meetings() -> list[BpdMeeting]:
    """Every non-cancelled meeting across all year-tables, newest first."""
    soup = BeautifulSoup(_fetch_html(), "html.parser")
    out: list[BpdMeeting] = []
    for table in soup.find_all("table"):
        year = _year_for(table)
        if year is None:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 8:
                continue
            name = _text(cells[1])
            meeting_date = _parse_date(_text(cells[2]), _text(cells[3]), year)
            if meeting_date is None:
                continue
            if _is_cancelled(name, _text(cells[6])):
                continue
            out.append(BpdMeeting(
                date=meeting_date,
                name=name,
                time=_text(cells[4]),
                agenda_url=_href(cells[6]),
                minutes_url=_href(cells[7]),
            ))
    out.sort(key=lambda m: (m.date, m.name), reverse=True)
    return out


def _year_for(table) -> int | None:
    """The year lives in the nearest non-empty <h2> above the table. Empty
    <h2></h2> elements sit between the tables, so skip past them."""
    node = table
    while True:
        node = node.find_previous("h2")
        if node is None:
            return None
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        m = re.search(r"\b(20\d{2})\b", text)
        return int(m.group(1)) if m else None


def _is_cancelled(name: str, agenda_cell: str) -> bool:
    """Status is glued onto the meeting name ('Regular Park Board Cancelled Due
    to Lack of Quorum') or written into the Agenda cell. A cancelled meeting can
    still have an agenda posted — it didn't happen, so it isn't a meeting."""
    return bool(_CANCELLED_RE.search(name) or _CANCELLED_RE.search(agenda_cell))


def _text(cell) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True).replace("\xa0", " ")).strip()


def _href(cell) -> str | None:
    a = cell.find("a", href=True)
    if a is None:
        return None
    href = a["href"].strip()
    return href if href.startswith("http") else None


def _slug(name: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")[:40]


def _parse_date(month: str, day: str, year: int) -> date | None:
    """Month name and bare day from separate cells, year from the heading."""
    day = re.sub(r"\D", "", day)
    if not day:
        return None
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(f"{month} {day} {year}", fmt).date()
        except ValueError:
            continue
    return None
