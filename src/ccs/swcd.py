"""Soil & Water Conservation District — scraper for /board-meetings/.

Page has three <h2> sections: Schedule, Agendas, Minutes. In Agendas and Minutes,
link text is the meeting date ('July 8, 2026') and href is the PDF. We join agendas
and minutes by date.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from .config import HTTP_HEADERS

URL = "https://boonecountyswcd.org/board-meetings/"


@dataclass(frozen=True)
class SwcdMeeting:
    date: date
    agenda_url: str | None
    minutes_url: str | None

    @property
    def key(self) -> str:
        return self.date.strftime("%Y%m%d")

    @property
    def name(self) -> str:
        return ""   # one body, one meeting per date — the body name is enough


def _fetch_html() -> str:
    r = requests.get(URL, headers=HTTP_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def list_meetings() -> list[SwcdMeeting]:
    soup = BeautifulSoup(_fetch_html(), "html.parser")
    agendas = _links_under(soup, "Agendas")
    minutes = _links_under(soup, "Minutes")
    all_dates = set(agendas) | set(minutes)
    out = [
        SwcdMeeting(date=d, agenda_url=agendas.get(d), minutes_url=minutes.get(d))
        for d in sorted(all_dates, reverse=True)
    ]
    return out


def _links_under(soup: BeautifulSoup, heading: str) -> dict[date, str]:
    """Walk siblings from the named <h2> until the next <h2>, collecting date→pdf-url."""
    h = _find_heading(soup, heading)
    if h is None:
        return {}
    out: dict[date, str] = {}
    for node in h.find_all_next():
        if node.name == "h2":
            break
        if node.name != "a" or not node.has_attr("href"):
            continue
        if not node["href"].lower().endswith(".pdf"):
            continue
        d = _parse_date(node.get_text(strip=True))
        if d is not None and d not in out:
            out[d] = node["href"]
    return out


def _find_heading(soup: BeautifulSoup, text: str):
    for h in soup.find_all("h2"):
        if h.get_text(strip=True).lower() == text.lower():
            return h
    return None


def _parse_date(s: str) -> date | None:
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None
