"""BoardDocs client — meeting list, agenda, agenda items, attached files.

All meetings for Boone County sit under a single 'committee' in BoardDocs
(BOARDDOCS_COMMITTEE_ID). Individual bodies are distinguished by meeting title.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .config import BOARDDOCS_BASE, BOARDDOCS_COMMITTEE_ID, BOARDDOCS_HEADERS


@dataclass(frozen=True)
class MeetingRef:
    """Lightweight meeting reference from the meetings-list endpoint."""
    unique: str        # short id used in all subsequent BD-Get* calls
    unid: str          # long id (kept for reference / dedup)
    title: str         # raw title, may include 'CANCELLED' prefix
    date: date         # parsed from numberdate (YYYYMMDD)


@dataclass(frozen=True)
class AgendaItem:
    unique: str
    unid: str
    title: str         # cleaned title from the agenda outline


@dataclass(frozen=True)
class PublicFile:
    unique: str
    filename: str
    url: str           # absolute URL


def _post(endpoint: str, body: str) -> requests.Response:
    url = f"{BOARDDOCS_BASE}/{endpoint}?open"
    r = requests.post(url, headers=BOARDDOCS_HEADERS, data=body, timeout=30)
    r.raise_for_status()
    return r


def list_meetings() -> list[MeetingRef]:
    """All meetings BoardDocs currently exposes for the county (thousands, ordered newest→oldest)."""
    r = _post("BD-GetMeetingsList", f"current_committee_id={BOARDDOCS_COMMITTEE_ID}")
    raw = json.loads(r.text)
    out: list[MeetingRef] = []
    for m in raw:
        d = m.get("numberdate", "")
        if not (d.isdigit() and len(d) == 8):
            continue
        out.append(MeetingRef(
            unique=m["unique"],
            unid=m["unid"],
            title=m.get("name", "").strip(),
            date=datetime.strptime(d, "%Y%m%d").date(),
        ))
    return out


def get_meeting_html(unique: str) -> str:
    r = _post("BD-GetMeeting", f"id={unique}&current_committee_id={BOARDDOCS_COMMITTEE_ID}")
    return r.text


def get_agenda_html(unique: str) -> str:
    r = _post("BD-GetAgenda", f"id={unique}&current_committee_id={BOARDDOCS_COMMITTEE_ID}")
    return r.text


def get_agenda_item_html(unique: str) -> str:
    r = _post("BD-GetAgendaItem", f"id={unique}&current_committee_id={BOARDDOCS_COMMITTEE_ID}")
    return r.text


def get_public_files_html(unique: str) -> str:
    r = _post("BD-GetPublicFiles", f"id={unique}&current_committee_id={BOARDDOCS_COMMITTEE_ID}")
    return r.text


def parse_meeting(meeting_html: str) -> dict[str, str]:
    """Extract the human-readable bits from a BD-GetMeeting response."""
    soup = BeautifulSoup(meeting_html, "html.parser")
    name = soup.select_one(".meeting-name")
    date_el = soup.select_one(".meeting-date")
    desc = soup.select_one(".meeting-description")
    return {
        "name": name.get_text(strip=True) if name else "",
        "date": date_el.get_text(strip=True) if date_el else "",
        "description": desc.get_text("\n", strip=True) if desc else "",
    }


def parse_agenda(agenda_html: str) -> list[AgendaItem]:
    """Parse agenda outline into an ordered list of items."""
    soup = BeautifulSoup(agenda_html, "html.parser")
    items: list[AgendaItem] = []
    for li in soup.select("li[unique][unid]"):
        title = li.get("Xtitle", "").strip()
        # Xtitle values often start with ' - ' — strip that
        title = re.sub(r"^\s*-\s*", "", title)
        items.append(AgendaItem(
            unique=li["unique"],
            unid=li["unid"],
            title=title,
        ))
    return items


def parse_agenda_item(item_html: str) -> dict[str, str]:
    """Extract the fielded content of an agenda item: subject, type, recommended action, etc."""
    soup = BeautifulSoup(item_html, "html.parser")
    fields: dict[str, str] = {}
    for row in soup.select("dl.row"):
        dt = row.select_one("dt.leftcol")
        dd = row.select_one("dd.rightcol")
        if dt and dd:
            fields[dt.get_text(strip=True)] = dd.get_text(" ", strip=True)
    return fields


def parse_public_files(files_html: str) -> list[PublicFile]:
    """Parse the attached-files response."""
    soup = BeautifulSoup(files_html, "html.parser")
    out: list[PublicFile] = []
    for a in soup.select("a.public-file[href]"):
        href = a["href"]
        url = href if href.startswith("http") else f"https://go.boarddocs.com{href}"
        out.append(PublicFile(
            unique=a.get("unique", ""),
            filename=a.get_text(strip=True),
            url=url,
        ))
    return out


def download_file(url: str, dest: Path) -> Path:
    """Download an attached file (usually PDF) to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=BOARDDOCS_HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 15):
                f.write(chunk)
    return dest


def public_url_for_meeting(unique: str) -> str:
    """The human-shareable BoardDocs URL for a meeting."""
    return f"{BOARDDOCS_BASE}/goto?open&id={unique}"
