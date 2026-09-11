"""Discovery + ingestion: finds meetings between `since` and today that
aren't already in the manifest, summarizes them, and records them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from . import bccd, diligent, manifest, summarize, swcd, youtube
from .config import Body, body_for_type_id, is_cancelled, tracked_bodies

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
    'Record' means a Diligent-listed, non-cancelled meeting, or a CD/SWCD entry
    with at least one PDF published.
    """
    today = today or date.today()
    tracked = tracked_bodies()
    dil_meetings = diligent.list_meetings(from_date=since, to_date=today)

    cd_cache: dict[str, list] = {}
    def cd_list(source: str, lister):
        if source not in cd_cache:
            try:
                cd_cache[source] = lister()
            except Exception:
                cd_cache[source] = []
        return cd_cache[source]

    results: list[tuple[str, bool]] = []
    for body in tracked:
        if body.source == "diligent":
            if body.type_id is None:
                has = False
            else:
                has = any(
                    m.type_id == body.type_id and not is_cancelled(m.title)
                    for m in dil_meetings
                )
        elif body.source == "bccd":
            has = any(
                since <= m.date <= today and (m.agenda_url or m.minutes_url)
                for m in cd_list("bccd", bccd.list_meetings)
            )
        elif body.source == "swcd":
            has = any(
                since <= m.date <= today and (m.agenda_url or m.minutes_url)
                for m in cd_list("swcd", swcd.list_meetings)
            )
        else:
            has = False
        results.append((body.display_name, has))
    return results


def sync_meetings(since: date, today: date | None = None) -> list[SectionEntry]:
    """Discover and ingest meetings between `since` and today, updating the manifest."""
    today = today or date.today()
    tracked = {b.id: b for b in tracked_bodies()}
    dil_meetings = diligent.list_meetings(from_date=since, to_date=today)
    youtube_videos = _try_list_youtube_streams()
    return _collect_recap(dil_meetings, youtube_videos, tracked, since, today)


def _collect_recap(dil_meetings: list[diligent.MeetingRef],
                   videos: list[youtube.YouTubeVideo] | None,
                   tracked: dict[str, Body],
                   since: date, today: date) -> list[SectionEntry]:
    already = manifest.load()
    entries: list[SectionEntry] = []

    for m in dil_meetings:
        if not (since <= m.date <= today):
            continue
        if is_cancelled(m.title):
            continue
        body = body_for_type_id(m.type_id)
        if body is None or body.id not in tracked:
            continue
        mid = manifest.make_id("diligent", str(m.id))
        if mid in already:
            entries.append(SectionEntry(body, m.date, m.title, already[mid]))
            continue
        print(f"  ingesting diligent: {m.date} {m.title[:60]}")
        record = summarize.ingest_diligent(m, body, videos=videos)
        manifest.upsert(record)
        entries.append(SectionEntry(body, m.date, m.title, record))

    for source_id, lister in (("bccd", bccd.list_meetings), ("swcd", swcd.list_meetings)):
        body = tracked.get(source_id)
        if body is None:
            continue
        try:
            meetings = lister()
        except Exception as e:
            print(f"  WARN: {source_id} list failed: {e}")
            continue
        for m in meetings:
            if not (since <= m.date <= today):
                continue
            if not (m.agenda_url or m.minutes_url):
                continue
            mid = manifest.make_id(source_id, m.date.strftime("%Y%m%d"))
            if mid in already:
                entries.append(SectionEntry(body, m.date, already[mid].title, already[mid]))
                continue
            print(f"  ingesting {source_id}: {m.date}")
            record = summarize.ingest_cd(source_id, m, body)
            manifest.upsert(record)
            entries.append(SectionEntry(body, m.date, record.title, record))

    entries.sort(key=lambda e: (e.meeting_date, e.body.id), reverse=True)
    return entries


def _try_list_youtube_streams() -> list[youtube.YouTubeVideo] | None:
    """YouTube listing is best-effort — sub-bodies have no video and yt-dlp can fail."""
    try:
        return youtube.list_streams(limit=100)
    except Exception as e:
        print(f"  WARN: YouTube listing failed: {e}. Continuing without transcripts.")
        return None
