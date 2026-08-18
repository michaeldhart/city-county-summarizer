"""Discovery + monthly-report orchestration.

Assembles a report with two sections:
  - Recap:     meetings between `since` and today, not already in the manifest.
  - Lookahead: meetings scheduled between today and `until`, agenda-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import bccd, diligent, manifest, summarize, swcd, templates, youtube
from .config import REPO_ROOT, Body, body_for_type_id, is_cancelled, tracked_bodies

REPORTS_DIR = REPO_ROOT / "reports"


@dataclass
class SectionEntry:
    body: Body
    meeting_date: date
    title: str
    record: manifest.MeetingRecord
    cancelled: bool = False


def check_sources(since: date, until: date) -> list[tuple[str, bool]]:
    """For each tracked body, return whether at least one record exists in [since, until].

    Cheap: no Claude calls, no per-item fetches — just the meeting-list endpoints.
    'Record' means a Diligent-listed, non-cancelled meeting, or a CD/SWCD entry
    with at least one PDF published.
    """
    tracked = tracked_bodies()
    dil_meetings = diligent.list_meetings(from_date=since, to_date=until)

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
                since <= m.date <= until and (m.agenda_url or m.minutes_url)
                for m in cd_list("bccd", bccd.list_meetings)
            )
        elif body.source == "swcd":
            has = any(
                since <= m.date <= until and (m.agenda_url or m.minutes_url)
                for m in cd_list("swcd", swcd.list_meetings)
            )
        else:
            has = False
        results.append((body.display_name, has))
    return results


def build_report(since: date, until: date, today: date | None = None) -> Path:
    today = today or date.today()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    tracked = {b.id: b for b in tracked_bodies()}
    dil_meetings = diligent.list_meetings(from_date=since, to_date=until)
    youtube_videos = _try_list_youtube_streams()

    recap = _collect_recap(dil_meetings, youtube_videos, tracked, since, today)
    lookahead = _collect_lookahead(dil_meetings, tracked, today, until)

    md = _render(since, until, today, recap, lookahead)
    out = REPORTS_DIR / f"{since.isoformat()}_to_{until.isoformat()}.md"
    out.write_text(md)
    return out


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


def _collect_lookahead(dil_meetings: list[diligent.MeetingRef],
                       tracked: dict[str, Body],
                       today: date, until: date) -> list[SectionEntry]:
    """Agenda-only previews for Diligent meetings in the coming window."""
    entries: list[SectionEntry] = []
    for m in dil_meetings:
        if not (today < m.date <= until):
            continue
        body = body_for_type_id(m.type_id)
        if body is None or body.id not in tracked:
            continue
        cancelled = is_cancelled(m.title)
        if cancelled:
            record = manifest.MeetingRecord(
                id=manifest.make_id("diligent-cancelled", str(m.id)),
                body_id=body.id, source="diligent",
                date=m.date.isoformat(), title=m.title,
                url=diligent.public_url_for_meeting(m.id),
            )
        else:
            print(f"  previewing: {m.date} {m.title[:60]}")
            record = summarize.summarize_diligent_lookahead(m, body)
        entries.append(SectionEntry(body, m.date, m.title, record, cancelled=cancelled))
    entries.sort(key=lambda e: (e.meeting_date, e.body.id))
    return entries


def _render(since: date, until: date, today: date,
            recap: list[SectionEntry], lookahead: list[SectionEntry]) -> str:
    parts: list[str] = [
        templates.REPORT_HEADER.format(
            start=templates.fmt_date(since),
            end=templates.fmt_date(until),
            generated=today.isoformat(),
            recap_start=since.isoformat(),
            recap_end=today.isoformat(),
            lookahead_start=today.isoformat(),
            lookahead_end=until.isoformat(),
        ),
        templates.SECTION_SEPARATOR,
        templates.RECAP_HEADING,
        _render_section(recap, empty=templates.RECAP_EMPTY),
        templates.SECTION_SEPARATOR,
        templates.LOOKAHEAD_HEADING,
        _render_section(lookahead, empty=templates.LOOKAHEAD_EMPTY),
    ]
    return "\n".join(parts).rstrip() + "\n"


def _render_section(entries: list[SectionEntry], *, empty: str) -> str:
    if not entries:
        return empty
    return "\n".join(_render_entry(e) for e in entries)


def _render_entry(e: SectionEntry) -> str:
    header_tpl = templates.ENTRY_HEADER_CANCELLED if e.cancelled else templates.ENTRY_HEADER
    lines: list[str] = [
        header_tpl.format(date=templates.fmt_date(e.meeting_date), body=e.body.display_name),
        "",
    ]
    if e.record.url:
        lines.append(templates.ENTRY_SOURCE_LINK.format(url=e.record.url))
        lines.append("")
    if e.cancelled or not e.record.summary_path:
        lines.append(templates.ENTRY_NO_SUMMARY)
        return "\n".join(lines)
    summary_path = REPO_ROOT / e.record.summary_path
    if summary_path.exists():
        # Bump heading levels so the summary's own H1 becomes H2, etc.
        for ln in summary_path.read_text().splitlines():
            lines.append("#" + ln if ln.startswith("#") else ln)
    else:
        lines.append(templates.ENTRY_SUMMARY_MISSING.format(path=e.record.summary_path))
    return "\n".join(lines)


def _try_list_youtube_streams() -> list[youtube.YouTubeVideo] | None:
    """YouTube listing is best-effort — sub-bodies have no video and yt-dlp can fail."""
    try:
        return youtube.list_streams(limit=100)
    except Exception as e:
        print(f"  WARN: YouTube listing failed: {e}. Continuing without transcripts.")
        return None
