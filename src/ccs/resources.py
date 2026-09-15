"""The raw materials behind a summary: portal pages, documents, videos.

Built during ingest and rendered as the meeting page's Resources column.

Attachments are the one kind that did NOT feed the summary: Diligent agendas
link backup PDFs via `/document/{guid}`, and nothing downloads them — only the
agenda HTML and the caption transcript reach Claude. They're listed anyway,
under their own heading, because they're the raw record behind an agenda item.
"""
from __future__ import annotations

from . import diligent
from .manifest import Resource

WATCH_URL = "https://www.youtube.com/watch?v={}"


def _video(video_id: str | None, has_transcript: bool) -> list[Resource]:
    if not video_id:
        return []
    label = "Video recording" if has_transcript else "Video recording (no captions)"
    return [Resource("video", label, WATCH_URL.format(video_id))]


def for_diligent(base: str, meeting_id: int, agenda_html: str,
                 video_id: str | None, has_transcript: bool) -> list[Resource]:
    out = [Resource("portal", "Diligent meeting page",
                    diligent.public_url_for_meeting(base, meeting_id))]
    out += _video(video_id, has_transcript)
    out += [Resource("attachment", a.label or "Untitled attachment", a.url)
            for a in diligent.extract_attachments(base, agenda_html)]
    return out


def for_pdf_meeting(agenda_url: str | None, minutes_url: str | None,
                    video_id: str | None, has_transcript: bool) -> list[Resource]:
    out = []
    if agenda_url:
        out.append(Resource("agenda", "Agenda (PDF)", agenda_url))
    if minutes_url:
        out.append(Resource("minutes", "Minutes (PDF)", minutes_url))
    out += _video(video_id, has_transcript)
    return out
