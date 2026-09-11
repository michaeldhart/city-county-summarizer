"""Discovery + monthly-report orchestration.

Assembles a report covering meetings between `since` and today that aren't
already in the manifest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import bccd, diligent, manifest, summarize, swcd, templates, youtube
from .config import REPO_ROOT, Body, body_for_type_id, is_cancelled, tracked_bodies

REPORTS_DIR = REPO_ROOT / "reports"

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


def build_report(since: date, today: date | None = None) -> Path:
    today = today or date.today()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    tracked = {b.id: b for b in tracked_bodies()}
    dil_meetings = diligent.list_meetings(from_date=since, to_date=today)
    youtube_videos = _try_list_youtube_streams()

    recap = _collect_recap(dil_meetings, youtube_videos, tracked, since, today)

    md = _render(since, today, recap)
    out = REPORTS_DIR / f"{since.isoformat()}_to_{today.isoformat()}.md"
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


def _render(since: date, today: date, recap: list[SectionEntry]) -> str:
    parts: list[str] = [
        templates.REPORT_HEADER.format(
            start=templates.fmt_date(since),
            end=templates.fmt_date(today),
            generated=today.isoformat(),
            recap_start=since.isoformat(),
            recap_end=today.isoformat(),
        ),
    ]
    toc = _render_toc(recap)
    if toc:
        parts.append(toc)
    parts.extend([
        templates.SECTION_SEPARATOR,
        templates.RECAP_HEADING,
        _render_section(recap, empty=templates.RECAP_EMPTY),
    ])
    return "\n".join(parts).rstrip() + "\n"


def _render_toc(recap: list[SectionEntry]) -> str:
    if not recap:
        return ""
    seen: dict[str, int] = {}
    noun = "meeting" if len(recap) == 1 else "meetings"
    lines = [
        templates.TOC_HEADING,
        templates.TOC_GROUP_HEADING.format(group="Recap", count=len(recap), noun=noun),
    ]
    for e in recap:
        text = _entry_link_text(e)
        lines.append(templates.TOC_ENTRY_LINE.format(text=text, anchor=_unique_slug(text, seen)))
    return "\n".join(lines)


def _entry_link_text(e: SectionEntry) -> str:
    body_label = clean_meeting_title(e.title) or e.body.display_name
    return f"{templates.fmt_date(e.meeting_date)} — {body_label}"


# GitHub anchor rules: lowercase; drop chars that are not word/space/hyphen
# (so punctuation like — , ( ) : & disappears rather than becoming a hyphen);
# then swap spaces for hyphens without collapsing runs, so double spaces
# survive as double hyphens — matching how GitHub itself slugs headings.
_SLUG_STRIP_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def _slugify(text: str) -> str:
    s = _SLUG_STRIP_RE.sub("", text.lower())
    s = s.replace(" ", "-")
    return s.strip("-")


def _unique_slug(text: str, seen: dict[str, int]) -> str:
    base = _slugify(text)
    count = seen.get(base, 0)
    seen[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def _render_section(entries: list[SectionEntry], *, empty: str) -> str:
    if not entries:
        return empty
    return "\n".join(_render_entry(e) for e in entries)


def _render_entry(e: SectionEntry) -> str:
    body_label = clean_meeting_title(e.title) or e.body.display_name
    lines: list[str] = [
        templates.ENTRY_HEADER.format(date=templates.fmt_date(e.meeting_date), body=body_label),
        "",
    ]
    if e.record.url:
        lines.append(templates.ENTRY_SOURCE_LINK.format(url=e.record.url))
        lines.append("")
    if not e.record.summary_path:
        lines.append(templates.ENTRY_NO_SUMMARY)
        return "\n".join(lines)
    summary_path = REPO_ROOT / e.record.summary_path
    if summary_path.exists():
        lines.extend(_bump_summary_headers(summary_path.read_text()))
    else:
        lines.append(templates.ENTRY_SUMMARY_MISSING.format(path=e.record.summary_path))
    return "\n".join(lines)


def _bump_summary_headers(summary: str) -> list[str]:
    """Nest a cached per-meeting summary under the entry wrapper.

    - Drop any leading '# ...' meeting-title header (legacy summaries wrote one;
      current prompts skip it because the wrapper already identifies the meeting).
    - Bump all remaining '#' headings by 2 so the summary's '## TL;DR' becomes
      '#### TL;DR' — one level below the '### entry header' wrapper.
    """
    raw_lines = summary.splitlines()
    out: list[str] = []
    header_stripped = False
    for ln in raw_lines:
        stripped = ln.lstrip()
        if not header_stripped and stripped.startswith("# ") and not stripped.startswith("## "):
            header_stripped = True
            continue
        out.append("##" + ln if ln.startswith("#") else ln)
    # Drop the blank line that usually follows the removed header
    while out and not out[0].strip():
        out.pop(0)
    return out


def _try_list_youtube_streams() -> list[youtube.YouTubeVideo] | None:
    """YouTube listing is best-effort — sub-bodies have no video and yt-dlp can fail."""
    try:
        return youtube.list_streams(limit=100)
    except Exception as e:
        print(f"  WARN: YouTube listing failed: {e}. Continuing without transcripts.")
        return None
