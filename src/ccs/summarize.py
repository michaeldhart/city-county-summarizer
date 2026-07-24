"""Ingest a single meeting end-to-end: pull sources, call Claude, save summary."""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

from . import bccd, boarddocs, manifest, pdftext, swcd, youtube
from .config import (
    CLAUDE_MODEL,
    MEETINGS_DIR,
    REPO_ROOT,
    Body,
    ensure_data_dirs,
    load_env,
)


def _meeting_dir(meeting_id: str) -> Path:
    ensure_data_dirs()
    d = MEETINGS_DIR / meeting_id.replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    return d


def ingest_boarddocs(ref: boarddocs.MeetingRef, body: Body,
                     videos: list[youtube.YouTubeVideo] | None = None) -> manifest.MeetingRecord:
    """Full recap pipeline: agenda, agenda items, attached files, video captions (if any), summary."""
    meeting_id = manifest.make_id("boarddocs", ref.unique)
    outdir = _meeting_dir(meeting_id)

    meeting_html = boarddocs.get_meeting_html(ref.unique)
    agenda_html = boarddocs.get_agenda_html(ref.unique)
    (outdir / "meeting.html").write_text(meeting_html)
    (outdir / "agenda.html").write_text(agenda_html)

    meeting = boarddocs.parse_meeting(meeting_html)
    items = boarddocs.parse_agenda(agenda_html)

    item_details: dict[str, dict[str, str]] = {}
    for item in items:
        html = boarddocs.get_agenda_item_html(item.unique)
        item_details[item.unique] = boarddocs.parse_agenda_item(html)
    (outdir / "items.json").write_text(json.dumps(item_details, indent=2))

    # Try to attach video captions for bodies that get recorded
    transcript = ""
    video_id: str | None = None
    if videos is not None:
        match = youtube.find_video(videos, ref.date, body.id)
        if match is not None:
            video_id = match.video_id
            vtt = youtube.download_captions(match.video_id, outdir)
            if vtt is not None:
                transcript = youtube.vtt_to_text(vtt)
                (outdir / "transcript.txt").write_text(transcript)

    prompt = _build_boarddocs_prompt(body, meeting, items, item_details, transcript, lookahead=False)
    summary = _call_claude(prompt)
    (outdir / "summary.md").write_text(summary)

    return manifest.MeetingRecord(
        id=meeting_id,
        body_id=body.id,
        source="boarddocs",
        date=ref.date.isoformat(),
        title=ref.title,
        url=boarddocs.public_url_for_meeting(ref.unique),
        video_id=video_id,
        has_transcript=bool(transcript),
        summary_path=str((outdir / "summary.md").relative_to(REPO_ROOT)),
    )


def summarize_boarddocs_lookahead(ref: boarddocs.MeetingRef, body: Body) -> manifest.MeetingRecord:
    """Agenda-only summary for an upcoming meeting."""
    meeting_id = manifest.make_id("boarddocs-preview", ref.unique)
    outdir = _meeting_dir(meeting_id)

    meeting_html = boarddocs.get_meeting_html(ref.unique)
    agenda_html = boarddocs.get_agenda_html(ref.unique)
    (outdir / "meeting.html").write_text(meeting_html)
    (outdir / "agenda.html").write_text(agenda_html)

    meeting = boarddocs.parse_meeting(meeting_html)
    items = boarddocs.parse_agenda(agenda_html)
    item_details: dict[str, dict[str, str]] = {}
    for item in items:
        item_details[item.unique] = boarddocs.parse_agenda_item(
            boarddocs.get_agenda_item_html(item.unique)
        )

    prompt = _build_boarddocs_prompt(body, meeting, items, item_details, transcript="", lookahead=True)
    summary = _call_claude(prompt)
    (outdir / "summary.md").write_text(summary)

    return manifest.MeetingRecord(
        id=meeting_id,
        body_id=body.id,
        source="boarddocs",
        date=ref.date.isoformat(),
        title=ref.title,
        url=boarddocs.public_url_for_meeting(ref.unique),
        summary_path=str((outdir / "summary.md").relative_to(REPO_ROOT)),
    )


def ingest_cd(source: str, meeting: bccd.BccdMeeting | swcd.SwcdMeeting,
              body: Body) -> manifest.MeetingRecord:
    """Recap for a Conservation District meeting (BCCD or SWCD): download PDFs, extract text, summarize."""
    date_key = meeting.date.strftime("%Y%m%d")
    meeting_id = manifest.make_id(source, date_key)
    outdir = _meeting_dir(meeting_id)

    agenda_text = _download_and_extract(meeting.agenda_url, outdir / "agenda.pdf", outdir / "agenda.txt")
    minutes_text = _download_and_extract(meeting.minutes_url, outdir / "minutes.pdf", outdir / "minutes.txt")

    prompt = _build_cd_prompt(body, meeting.date, agenda_text, minutes_text)
    summary = _call_claude(prompt)
    (outdir / "summary.md").write_text(summary)

    return manifest.MeetingRecord(
        id=meeting_id,
        body_id=body.id,
        source=source,
        date=meeting.date.isoformat(),
        title=f"{body.display_name} — {meeting.date.strftime('%B %-d, %Y')}",
        url=meeting.agenda_url or meeting.minutes_url,
        summary_path=str((outdir / "summary.md").relative_to(REPO_ROOT)),
    )


def _download_and_extract(url: str | None, pdf_dest: Path, txt_dest: Path) -> str:
    if not url:
        return ""
    try:
        pdftext.download_pdf(url, pdf_dest)
        text = pdftext.pdf_to_text(pdf_dest)
    except Exception as e:
        return f"[Failed to extract from {url}: {e}]"
    txt_dest.write_text(text)
    return text


def _build_boarddocs_prompt(body: Body, meeting: dict[str, str],
                            items: list[boarddocs.AgendaItem],
                            item_details: dict[str, dict[str, str]],
                            transcript: str, lookahead: bool) -> str:
    agenda_lines: list[str] = []
    for it in items:
        d = item_details.get(it.unique, {})
        agenda_lines.append(f"\n--- {it.title} ---")
        for k, v in d.items():
            agenda_lines.append(f"{k}: {v}")
    agenda_block = "\n".join(agenda_lines)

    mode = "upcoming agenda" if lookahead else "meeting recap"
    header = f"# {body.display_name} — {meeting['date']}"

    if lookahead:
        instructions = (
            "This is an UPCOMING meeting. Summarize what's on the agenda so the reader knows "
            "what to expect. Group by category. Flag items that look consequential (large "
            "dollar amounts, zoning changes, appointments, ordinances)."
        )
    else:
        instructions = (
            "This meeting has already occurred. Produce a Markdown recap with these sections:\n"
            "## TL;DR (3–5 bullets: most important decisions and discussions)\n"
            "## Attendance & housekeeping\n"
            "## Decisions & votes (each with vote count and notable discussion or dissent)\n"
            "## Discussion items (no vote)\n"
            "## Public comment\n"
            "## Notable moments (anything colorful, tense, or unusual)\n"
        )

    transcript_block = f"\n===== TRANSCRIPT =====\n{transcript}" if transcript else ""
    transcript_note = "" if transcript else (
        "\nNote: no video transcript is available for this meeting — work from the agenda only.\n"
    )

    return (
        f"You are summarizing a Boone County, IL government meeting for a personal briefing.\n"
        f"Body: {body.display_name}\n"
        f"Meeting: {meeting['name']} — {meeting['date']}\n"
        f"Mode: {mode}\n\n"
        f"{instructions}\n"
        f"Do not invent details not in the source. If the transcript has typos "
        f"(auto-captions), silently correct obvious ones; quote sparingly.\n"
        f"Start the response with:\n{header}\n"
        f"{transcript_note}"
        f"\n===== MEETING DESCRIPTION =====\n{meeting['description']}\n"
        f"\n===== AGENDA =====\n{agenda_block}\n"
        f"{transcript_block}\n"
    )


def _build_cd_prompt(body: Body, meeting_date, agenda: str, minutes: str) -> str:
    header = f"# {body.display_name} — {meeting_date.strftime('%B %-d, %Y')}"
    return (
        f"You are summarizing a Boone County, IL Conservation District meeting for a personal briefing.\n"
        f"Body: {body.display_name}\n"
        f"Date: {meeting_date.isoformat()}\n\n"
        f"Produce a Markdown recap with these sections:\n"
        f"## TL;DR (3–5 bullets)\n"
        f"## Decisions & votes\n"
        f"## Discussion items\n"
        f"## Financial / operational notes\n\n"
        f"If minutes are missing, work from the agenda only and label the summary '## Agenda preview'.\n"
        f"Do not invent details.\n"
        f"Start the response with:\n{header}\n"
        f"\n===== AGENDA (PDF text) =====\n{agenda or '[no agenda available]'}\n"
        f"\n===== MINUTES (PDF text) =====\n{minutes or '[no minutes available]'}\n"
    )


def _call_claude(prompt: str) -> str:
    load_env()
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
