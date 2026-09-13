"""Discovery + ingestion: finds meetings between `since` and today that
aren't already in the manifest, summarizes them, and records them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from . import diligent, manifest, sources, summarize, youtube
from .config import (
    JURISDICTIONS_BY_ID,
    Body,
    body_for_type_id,
    is_cancelled,
    tracked_bodies,
)

_TRAILING_DATE_RE = re.compile(
    r"\s*[-—]\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\s*$",
    re.IGNORECASE,
)
_CANCELLED_PREFIX_RE = re.compile(r"^\s*CANCELLED(?:/RESCHEDULED)?\s+", re.IGNORECASE)


def clean_meeting_title(raw_title: str) -> str:
    s = _CANCELLED_PREFIX_RE.sub("", raw_title)
    s = _TRAILING_DATE_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class SectionEntry:
    body: Body
    meeting_date: date
    title: str
    record: manifest.MeetingRecord


def check_sources(since: date, today: date | None = None) -> list[tuple[str, bool]]:
    """For each tracked body, return whether at least one record exists in [since, today].

    Cheap: no Claude calls, no per-item fetches — just the meeting-list endpoints.
    'Record' means a Diligent-listed, non-cancelled meeting, or a PDF-index entry
    with at least one document published.
    """
    today = today or date.today()
    tracked = tracked_bodies()
    dil_by_source = _diligent_meetings(tracked, since, today)
    pdf_by_source = _pdf_index_meetings(tracked)

    results: list[tuple[str, bool]] = []
    for body in tracked:
        src = sources.SOURCES.get(body.source)
        if isinstance(src, sources.DiligentSource):
            has = body.type_id is not None and any(
                m.type_id == body.type_id and not is_cancelled(m.title)
                for m in dil_by_source.get(body.source, [])
            )
        elif isinstance(src, sources.PdfIndexSource):
            has = any(
                since <= m.date <= today and (m.agenda_url or m.minutes_url)
                for m in pdf_by_source.get(body.source, [])
            )
        else:
            has = False
        results.append((body.display_name, has))
    return results


def sync_meetings(since: date, today: date | None = None) -> list[SectionEntry]:
    """Discover and ingest meetings between `since` and today, updating the manifest."""
    today = today or date.today()
    tracked = tracked_bodies()
    dil_by_source = _diligent_meetings(tracked, since, today)
    videos = list_videos_by_jurisdiction(tracked)
    return _collect_recap(dil_by_source, videos, tracked, since, today)


def _diligent_meetings(tracked: list[Body], since: date,
                       today: date) -> dict[str, list[diligent.MeetingRef]]:
    """One meetings-list call per Diligent tenant represented in `tracked`."""
    out: dict[str, list[diligent.MeetingRef]] = {}
    for source in sorted({b.source for b in tracked
                          if isinstance(sources.SOURCES.get(b.source), sources.DiligentSource)}):
        try:
            out[source] = diligent.list_meetings(
                sources.diligent_base(source), from_date=since, to_date=today,
            )
        except Exception as e:
            print(f"  WARN: {source} meeting list failed: {e}")
            out[source] = []
    return out


def _pdf_index_meetings(tracked: list[Body]) -> dict[str, list]:
    out: dict[str, list] = {}
    for source in sorted({b.source for b in tracked
                          if isinstance(sources.SOURCES.get(b.source), sources.PdfIndexSource)}):
        try:
            out[source] = sources.pdf_index_lister(source)()
        except Exception as e:
            print(f"  WARN: {source} list failed: {e}")
            out[source] = []
    return out


def _collect_recap(dil_by_source: dict[str, list[diligent.MeetingRef]],
                   videos_by_jurisdiction: dict[str, list[youtube.YouTubeVideo]],
                   tracked: list[Body],
                   since: date, today: date) -> list[SectionEntry]:
    already = manifest.load()
    tracked_ids = {b.id for b in tracked}
    entries: list[SectionEntry] = []

    for source, meetings in dil_by_source.items():
        base = sources.diligent_base(source)
        for m in meetings:
            if not (since <= m.date <= today):
                continue
            if is_cancelled(m.title):
                continue
            body = body_for_type_id(source, m.type_id)
            if body is None or body.id not in tracked_ids:
                continue
            mid = manifest.make_id(source, str(m.id))
            if mid in already:
                entries.append(SectionEntry(body, m.date, m.title, already[mid]))
                continue
            print(f"  ingesting {source}: {m.date} {m.title[:60]}")
            record = summarize.ingest_diligent(
                base, source, m, body,
                videos=videos_by_jurisdiction.get(body.jurisdiction_id),
            )
            manifest.upsert(record)
            entries.append(SectionEntry(body, m.date, m.title, record))

    pdf_by_source = _pdf_index_meetings(tracked)
    for body in tracked:
        if not isinstance(sources.SOURCES.get(body.source), sources.PdfIndexSource):
            continue
        for m in pdf_by_source.get(body.source, []):
            if not (since <= m.date <= today):
                continue
            if not (m.agenda_url or m.minutes_url):
                continue
            mid = manifest.make_id(body.source, m.date.strftime("%Y%m%d"))
            if mid in already:
                entries.append(SectionEntry(body, m.date, already[mid].title, already[mid]))
                continue
            print(f"  ingesting {body.source}: {m.date}")
            record = summarize.ingest_pdf_meeting(body.source, m, body)
            manifest.upsert(record)
            entries.append(SectionEntry(body, m.date, record.title, record))

    entries.sort(key=lambda e: (e.meeting_date, e.body.id), reverse=True)
    return entries


def list_videos_by_jurisdiction(
    tracked: list[Body],
) -> dict[str, list[youtube.YouTubeVideo]]:
    """Best-effort per-channel listing — sub-bodies have no video and yt-dlp can fail."""
    out: dict[str, list[youtube.YouTubeVideo]] = {}
    for jid in sorted({b.jurisdiction_id for b in tracked}):
        j = JURISDICTIONS_BY_ID[jid]
        if j.youtube_channel_id is None:
            continue
        try:
            out[jid] = youtube.list_videos(j.youtube_channel_id, j.youtube_tab, limit=100)
        except Exception as e:
            print(f"  WARN: YouTube listing for {j.display_name} failed: {e}. "
                  f"Continuing without transcripts.")
    return out
