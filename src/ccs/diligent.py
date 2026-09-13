"""Diligent Community client — Boone County migrated here from BoardDocs around May 2026.

Public REST API — no auth, no session, just a User-Agent header. Meeting list is
one call with a date range; each meeting's agenda comes back as one HTML blob
(rendered from the source .docx) rather than as individually-fetchable items.

Every call takes the tenant's `base` URL. The same product is served under
several hostname families (*.diligentoneplatform.com, *.highbond.com), so one
client serves every tenant — but meeting ids are only unique within a tenant.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import requests

from .config import HTTP_HEADERS


@dataclass(frozen=True)
class MeetingRef:
    """Lightweight meeting reference from the meetings-list endpoint."""
    id: int
    title: str          # e.g. "Boone County Board Meeting - Jul 16 2026"
    date: date
    type_id: int        # numeric body id — see config.Body.type_id
    type_name: str
    published: bool
    location: str
    time: str           # e.g. "06:30 PM"


@dataclass(frozen=True)
class MeetingData:
    """Detail from BD-like /meetingData endpoint."""
    id: int
    name: str
    location: str
    time: str
    type_id: int
    members: list[str]
    in_past: bool
    live: bool
    historic: bool


@dataclass(frozen=True)
class MeetingDocument:
    """One document attached at the meeting level. Type 1 = HTML agenda, 4 = PDF."""
    id: int
    name: str
    document_type: int
    format: str
    html: str            # empty for PDFs
    agenda_cover: str    # HTML snippet (title, date, location)


@dataclass(frozen=True)
class Attachment:
    """A file linked from within the agenda HTML (usually a PDF backup document)."""
    guid: str
    label: str
    url: str


def _get(base: str, path: str, **params) -> requests.Response:
    url = f"{base}{path}"
    r = requests.get(url, headers=HTTP_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r


def list_meetings(base: str, from_date: date | None = None,
                  to_date: date | None = None) -> list[MeetingRef]:
    """Meetings in [from_date, to_date] inclusive. Wide open by default."""
    if from_date is None:
        from_date = date(2010, 1, 1)
    if to_date is None:
        to_date = date(9999, 12, 31)
    r = _get(
        base,
        "/Services/MeetingsService.svc/meetings",
        **{"from": from_date.isoformat(), "to": to_date.isoformat(), "loadall": "false"},
    )
    raw = r.json()
    out: list[MeetingRef] = []
    for m in raw:
        d = m.get("MeetingDate", "")
        try:
            parsed = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append(MeetingRef(
            id=int(m["Id"]),
            title=m.get("Name", "").strip(),
            date=parsed,
            type_id=int(m.get("MeetingTypeId", 0)),
            type_name=m.get("MeetingTypeName", "").strip(),
            published=bool(m.get("Published", False)),
            location=m.get("MeetingLocation", "").strip(),
            time=m.get("MeetingTime", "").strip(),
        ))
    return out


def get_meeting_data(base: str, meeting_id: int) -> MeetingData:
    r = _get(base, f"/Services/MeetingsService.svc/meetings/{meeting_id}/meetingData")
    d = r.json()
    return MeetingData(
        id=int(d.get("Id", meeting_id)),
        name=d.get("Name", "").strip(),
        location=d.get("Location", "").strip(),
        time=d.get("Time", "").strip(),
        type_id=int(d.get("TypeId", 0)),
        members=list(d.get("Members", [])),
        in_past=bool(d.get("InPast", False)),
        live=bool(d.get("Live", False)),
        historic=bool(d.get("Historic", False)),
    )


def get_meeting_documents(base: str, meeting_id: int) -> list[MeetingDocument]:
    r = _get(base, f"/Services/MeetingsService.svc/meetings/{meeting_id}/meetingDocuments")
    raw = r.json().get("Documents", [])
    return [
        MeetingDocument(
            id=int(d.get("Id", 0)),
            name=d.get("Name", "").strip(),
            document_type=int(d.get("DocumentType", 0)),
            format=d.get("Format", "").strip(),
            html=d.get("Html", ""),
            agenda_cover=d.get("AgendaCover", ""),
        )
        for d in raw
    ]


def get_video_id(base: str, meeting_id: int) -> str | None:
    """The tenant's own YouTube id for a meeting, if it publishes one.

    District 100 populates this; Boone County leaves it empty and has to fall
    through to youtube.find_video() by title+date. The payload is JSON encoded
    *inside* a JSON string, so it needs decoding twice.
    """
    try:
        payload = _get(base, f"/api/videolink/{meeting_id}").json()
    except Exception:
        return None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return payload or None
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return None
    for entry in payload:
        if isinstance(entry, dict) and entry.get("YouTubeEventId"):
            return entry["YouTubeEventId"]
    return None


def extract_attachments(base: str, agenda_html: str) -> list[Attachment]:
    """Pull /document/{guid} links out of the agenda HTML with their visible link text."""
    seen: set[str] = set()
    out: list[Attachment] = []
    # Match <a href="/document/GUID">label</a>
    for m in re.finditer(
        r'<a[^>]*href="(/document/[0-9a-f-]+)"[^>]*>(.*?)</a>',
        agenda_html, flags=re.DOTALL | re.IGNORECASE,
    ):
        href = m.group(1)
        if href in seen:
            continue
        seen.add(href)
        label = re.sub(r"<[^>]+>", " ", m.group(2))
        label = re.sub(r"\s+", " ", label).strip()
        guid = href.rsplit("/", 1)[-1]
        out.append(Attachment(guid=guid, label=label, url=f"{base}{href}"))
    return out


def download_document(base: str, guid_or_id: str, dest: Path) -> Path:
    """Download an attached document (PDF, docx-rendered, etc.) to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{base}/document/{guid_or_id}"
    with requests.get(url, headers=HTTP_HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 15):
                f.write(chunk)
    return dest


def public_url_for_meeting(base: str, meeting_id: int) -> str:
    # Org=Cal is redundant on some tenants but accepted everywhere; keeping it
    # leaves already-published Boone County meeting URLs byte-identical.
    return f"{base}/Portal/MeetingInformation.aspx?Org=Cal&Id={meeting_id}"


def agenda_html_to_text(html: str) -> str:
    """Strip the CSS-in-HTML and tags to leave clean readable agenda text."""
    if not html:
        return ""
    # Kill <style>, <script>, and Aspose's CSS resets inside <head>
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<head[^>]*>.*?</head>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Drop tags but keep text
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</h[1-6]>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</li>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
