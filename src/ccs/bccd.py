"""Boone County Conservation District — scraper for /board-meetings/.

Page structure: one <table> per year. Header row is `Date | Agenda | Minutes`.
Each subsequent row is a meeting: 'January 20', <a>agenda</a>, <a>minutes</a>.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from .config import HTTP_HEADERS

URL = "https://www.bccdil.org/board-meetings/"


@dataclass(frozen=True)
class BccdMeeting:
    date: date
    agenda_url: str | None
    minutes_url: str | None

    @property
    def key(self) -> str:
        return self.date.strftime("%Y%m%d")

    @property
    def body_id(self):
        return None   # single-body source

    @property
    def name(self) -> str:
        return ""   # one body, one meeting per date — the body name is enough


def _fetch_html() -> str:
    r = requests.get(URL, headers=HTTP_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def list_meetings() -> list[BccdMeeting]:
    """Parse all year-tables into an ordered list of meetings, newest first."""
    soup = BeautifulSoup(_fetch_html(), "html.parser")
    out: list[BccdMeeting] = []
    for table in soup.find_all("table"):
        year = _year_from_table(table)
        if year is None:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td"])
            if len(cells) < 3:
                continue
            date_str = cells[0].get_text(" ", strip=True)
            meeting_date = _parse_date(date_str, year)
            if meeting_date is None:
                continue
            agenda_a = cells[1].find("a", href=True)
            minutes_a = cells[2].find("a", href=True)
            out.append(BccdMeeting(
                date=meeting_date,
                agenda_url=agenda_a["href"] if agenda_a else None,
                minutes_url=minutes_a["href"] if minutes_a else None,
            ))
    out.sort(key=lambda m: m.date, reverse=True)
    return out


def _year_from_table(table) -> int | None:
    """The year is in a <th> in the first row of each table."""
    first_tr = table.find("tr")
    if not first_tr:
        return None
    text = first_tr.get_text(" ", strip=True)
    m = re.search(r"\b(20\d{2})\b", text)
    return int(m.group(1)) if m else None


def _parse_date(date_str: str, year: int) -> date | None:
    """Turn 'January 20' + year into a real date. Silently returns None on garbage."""
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", date_str).strip()
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(f"{cleaned} {year}", fmt).date()
        except ValueError:
            continue
    return None
