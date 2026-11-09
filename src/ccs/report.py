"""Discovery + ingestion: finds meetings between `since` and today that
aren't already in the manifest, summarizes them, and records them.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Iterator

from . import diligent, manifest, resources, sources, summarize, youtube
from .config import (
    JURISDICTIONS_BY_ID,
    Body,
    body_for_meeting,
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

# Checking a stored meeting for newly posted sources costs nothing (the
# listings are fetched anyway), so the look-back is long. Reading them is not
# free: a meeting whose refresh keeps finding nothing is retried this many
# times and then left alone.
REFRESH_DAYS = 365
MAX_REFRESH_ATTEMPTS = 4


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


def select_bodies(only: set | None = None) -> list[Body]:
    """Tracked bodies, optionally narrowed by body id, source, or jurisdiction.

    Phase catch-up runs need this: a bare `--since 2026-01-01` would backfill
    every government at once rather than just the one being added.
    """
    tracked = tracked_bodies()
    if not only:
        return tracked
    return [b for b in tracked
            if b.id in only or b.source in only or b.jurisdiction_id in only]


def check_sources(since: date, today: date | None = None,
                  only: set | None = None) -> list[tuple[str, bool]]:
    """For each tracked body, return whether at least one record exists in [since, today].

    Cheap: no Claude calls, no per-item fetches — just the meeting-list endpoints.
    'Record' means a Diligent-listed, non-cancelled meeting, or a PDF-index entry
    with at least one document published.
    """
    today = today or date.today()
    tracked = select_bodies(only)
    dil_by_source = _diligent_meetings(tracked, since, today)
    pdf_by_source = _pdf_index_meetings(tracked)

    results: list[tuple[str, bool]] = []
    for body in tracked:
        src = sources.SOURCES.get(body.source)
        if isinstance(src, sources.DiligentSource):
            has = any(
                body_for_meeting(body.source, m.type_id, m.title) is body
                and not is_cancelled(m.title)
                for m in dil_by_source.get(body.source, [])
            )
        elif isinstance(src, sources.PdfIndexSource):
            has = any(
                m.body_id in (None, body.id)
                and since <= m.date <= today and (m.agenda_url or m.minutes_url)
                for m in pdf_by_source.get(body.source, [])
            )
        else:
            has = False
        results.append((body.display_name, has))
    return results


def sync_meetings(since: date, today: date | None = None, only: set | None = None,
                  refresh: bool = True) -> tuple[list[SectionEntry], list[str]]:
    """Discover and ingest meetings between `since` and today, updating the manifest.

    With `refresh`, meetings already stored are also re-checked for sources
    posted since, as far back as REFRESH_DAYS. Also returns a line for each
    published document that could not be read.
    """
    today = today or date.today()
    tracked = select_bodies(only)
    list_from = min(since, today - timedelta(days=REFRESH_DAYS)) if refresh else since
    dil_by_source = _diligent_meetings(tracked, list_from, today)
    videos = list_videos_by_jurisdiction(tracked)
    return _collect_recap(dil_by_source, videos, tracked, since, today, refresh)


def find_gaps(today: date | None = None,
              only: set | None = None) -> list[tuple[manifest.MeetingRecord, str]]:
    """Stored meetings a refresh would act on, and why. Free: no ingest, no Claude."""
    today = today or date.today()
    tracked = select_bodies(only)
    dil_by_source = _diligent_meetings(tracked, today - timedelta(days=REFRESH_DAYS), today)
    videos = list_videos_by_jurisdiction(tracked)
    known = _known_meetings(dil_by_source, _pdf_index_meetings(tracked), tracked,
                            manifest.load(), today)
    return _refresh_existing(known, videos, [], dry_run=True)


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


def _known_meetings(dil_by_source: dict[str, list[diligent.MeetingRef]],
                    pdf_by_source: dict[str, list], tracked: list[Body],
                    already: dict[str, manifest.MeetingRecord],
                    today: date) -> Iterator[tuple]:
    """(record, body, listed meeting, tenant base or None) for each stored meeting
    that is still on its source's listing and inside the refresh look-back."""
    tracked_ids = {b.id for b in tracked}
    oldest = today - timedelta(days=REFRESH_DAYS)

    for source, meetings in dil_by_source.items():
        base = sources.diligent_base(source)
        for m in meetings:
            if not (oldest <= m.date <= today) or is_cancelled(m.title):
                continue
            body = body_for_meeting(source, m.type_id, m.title)
            if body is None or body.id not in tracked_ids:
                continue
            record = already.get(manifest.make_id(source, str(m.id)))
            if record is not None:
                yield record, body, m, base

    for body in tracked:
        if not isinstance(sources.SOURCES.get(body.source), sources.PdfIndexSource):
            continue
        for m in pdf_by_source.get(body.source, []):
            if m.body_id is not None and m.body_id != body.id:
                continue
            if not (oldest <= m.date <= today) or not (m.agenda_url or m.minutes_url):
                continue
            record = already.get(manifest.make_id(body.source, m.key))
            if record is not None:
                yield record, body, m, None


def _refresh_reason(record: manifest.MeetingRecord, videos: list[youtube.YouTubeVideo] | None,
                    pdf_meeting=None,
                    tenant_video: Callable[[], str | None] | None = None) -> str | None:
    """Why a stored meeting is worth re-reading, or None. Cheap: works from
    listings already in hand; `tenant_video` is the one lookup that costs a request."""
    if record.refresh_attempts >= MAX_REFRESH_ATTEMPTS:
        return None
    kinds = {r.kind for r in record.resources}
    if pdf_meeting is not None:
        if pdf_meeting.minutes_url and "minutes" not in kinds:
            return "minutes posted"
        if pdf_meeting.agenda_url and "agenda" not in kinds:
            return "agenda posted"
    if record.has_transcript:
        return None
    if record.video_id:
        return "captions may be ready"
    found = youtube.find_video(videos or [], date.fromisoformat(record.date), record.body_id)
    if found is not None or (tenant_video is not None and tenant_video()):
        return "video posted"
    return None


def _refresh_existing(known: Iterator[tuple], videos_by_jurisdiction: dict[str, list],
                      unread: list[str], dry_run: bool = False) -> list[tuple]:
    """Re-read stored meetings whose sources have grown. Rewrites the summary only
    when something new is readable; otherwise just counts the attempt."""
    done: list[tuple] = []
    for record, body, m, base in known:
        videos = videos_by_jurisdiction.get(body.jurisdiction_id)
        tenant = ((lambda: diligent.get_video_id(base, m.id))
                  if base and record.video_id is None else None)
        reason = _refresh_reason(record, videos, None if base else m, tenant)
        if reason is None:
            continue
        done.append((record, reason))
        if dry_run:
            continue

        print(f"  refreshing {record.id}: {reason}")
        try:
            if base:
                new = summarize.ingest_diligent(base, record.source, m, body,
                                                videos=videos, previous=record)
            else:
                new = summarize.ingest_pdf_meeting(body.source, m, body,
                                                   videos=videos, previous=record)
        except (summarize.Unchanged, summarize.NoUsableText) as e:
            print(f"  nothing new: {e}")
            new = dataclasses.replace(record, refresh_attempts=record.refresh_attempts + 1)
            seen = getattr(e, "video_id", None)
            if seen and seen != record.video_id:
                new = dataclasses.replace(
                    new, video_id=seen, resources=resources.add_video(record.resources, seen))
            if not base:
                kinds = {r.kind for r in record.resources}
                for kind, url in (("minutes", m.minutes_url), ("agenda", m.agenda_url)):
                    if url and kind not in kinds:
                        unread.append(f"{record.id}: {kind} published but could not be read")
            manifest.store(new)
            continue
        manifest.upsert(new)
    return done


def _collect_recap(dil_by_source: dict[str, list[diligent.MeetingRef]],
                   videos_by_jurisdiction: dict[str, list[youtube.YouTubeVideo]],
                   tracked: list[Body],
                   since: date, today: date,
                   refresh: bool = True) -> tuple[list[SectionEntry], list[str]]:
    pdf_by_source = _pdf_index_meetings(tracked)
    unread: list[str] = []
    if refresh:
        _refresh_existing(
            _known_meetings(dil_by_source, pdf_by_source, tracked, manifest.load(), today),
            videos_by_jurisdiction, unread)

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
            body = body_for_meeting(source, m.type_id, m.title)
            if body is None or body.id not in tracked_ids:
                continue
            mid = manifest.make_id(source, str(m.id))
            if mid in already:
                entries.append(SectionEntry(body, m.date, m.title, already[mid]))
                continue
            print(f"  ingesting {source}: {m.date} {m.title[:60]}")
            try:
                record = summarize.ingest_diligent(
                    base, source, m, body,
                    videos=videos_by_jurisdiction.get(body.jurisdiction_id),
                )
            except summarize.NoUsableText as e:
                # Not a failure: the county often posts its agenda late.
                print(f"  skipped: {e}")
                continue
            manifest.upsert(record)
            entries.append(SectionEntry(body, m.date, m.title, record))

    for body in tracked:
        if not isinstance(sources.SOURCES.get(body.source), sources.PdfIndexSource):
            continue
        for m in pdf_by_source.get(body.source, []):
            if m.body_id is not None and m.body_id != body.id:
                continue      # one site, several bodies
            if not (since <= m.date <= today):
                continue
            if not (m.agenda_url or m.minutes_url):
                continue
            mid = manifest.make_id(body.source, m.key)
            if mid in already:
                entries.append(SectionEntry(body, m.date, already[mid].title, already[mid]))
                continue
            print(f"  ingesting {body.source}: {m.date}")
            try:
                record = summarize.ingest_pdf_meeting(
                    body.source, m, body,
                    videos=videos_by_jurisdiction.get(body.jurisdiction_id),
                )
            except summarize.NoUsableText as e:
                print(f"  skipped: {e}")
                unread.append(str(e))
                continue
            kinds = {r.kind for r in record.resources}
            if (m.agenda_url and "agenda" not in kinds) or (m.minutes_url and "minutes" not in kinds):
                unread.append(f"{mid}: published without a document it could not read")
            manifest.upsert(record)
            entries.append(SectionEntry(body, m.date, record.title, record))

    entries.sort(key=lambda e: (e.meeting_date, e.body.id), reverse=True)
    return entries, unread


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
            # Belvidere's channel holds 419 videos back to 2018; a low cap
            # silently truncates the archive and drops older matches.
            out[jid] = youtube.list_videos(j.youtube_channel_id, j.youtube_tab, limit=500)
        except Exception as e:
            print(f"  WARN: YouTube listing for {j.display_name} failed: {e}. "
                  f"Continuing without transcripts.")
    return out
