"""Ingest a single meeting end-to-end: pull sources, call Claude, save summary."""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

from . import diligent, manifest, pdftext, youtube
from .config import (
    CLAUDE_MODEL,
    MEETINGS_DIR,
    REPO_ROOT,
    Body,
    ensure_data_dirs,
    jurisdiction_for,
    load_env,
)


def _meeting_dir(meeting_id: str) -> Path:
    ensure_data_dirs()
    d = MEETINGS_DIR / meeting_id.replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    return d


def ingest_diligent(base: str, source: str, ref: diligent.MeetingRef, body: Body,
                    videos: list[youtube.YouTubeVideo] | None = None) -> manifest.MeetingRecord:
    """Full recap pipeline: metadata, agenda HTML, video captions (if any), summary."""
    meeting_id = manifest.make_id(source, str(ref.id))
    outdir = _meeting_dir(meeting_id)

    meeting_data = diligent.get_meeting_data(base, ref.id)
    documents = diligent.get_meeting_documents(base, ref.id)
    (outdir / "meeting_data.json").write_text(json.dumps(_dataclass_to_dict(meeting_data), indent=2))
    for doc in documents:
        if doc.html:
            (outdir / f"document_{doc.id}.html").write_text(doc.html)

    agenda_doc = next((d for d in documents if d.document_type == 1 and d.html), None)
    agenda_text = diligent.agenda_html_to_text(agenda_doc.html) if agenda_doc else ""

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

    prompt = _build_diligent_prompt(body, meeting_data, ref, agenda_text, transcript)
    summary = _call_claude(prompt)
    (outdir / "summary.md").write_text(summary)

    return manifest.MeetingRecord(
        id=meeting_id,
        body_id=body.id,
        source=source,
        date=ref.date.isoformat(),
        title=ref.title,
        url=diligent.public_url_for_meeting(base, ref.id),
        video_id=video_id,
        has_transcript=bool(transcript),
        summary_path=str((outdir / "summary.md").relative_to(REPO_ROOT)),
    )


def ingest_pdf_meeting(source: str, meeting, body: Body) -> manifest.MeetingRecord:
    """Recap for a site that posts agenda/minutes PDFs: download, extract, summarize.

    `meeting` is any object exposing `.date`, `.agenda_url` and `.minutes_url`.
    """
    date_key = meeting.date.strftime("%Y%m%d")
    meeting_id = manifest.make_id(source, date_key)
    outdir = _meeting_dir(meeting_id)

    agenda_text = _download_and_extract(meeting.agenda_url, outdir / "agenda.pdf", outdir / "agenda.txt")
    minutes_text = _download_and_extract(meeting.minutes_url, outdir / "minutes.pdf", outdir / "minutes.txt")

    prompt = _build_pdf_meeting_prompt(body, meeting.date, agenda_text, minutes_text)
    summary = _call_claude(prompt)
    (outdir / "summary.md").write_text(summary)

    return manifest.MeetingRecord(
        id=meeting_id,
        body_id=body.id,
        source=source,
        date=meeting.date.isoformat(),
        title=body.display_name,
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


def _build_diligent_prompt(body: Body, data: diligent.MeetingData,
                           ref: diligent.MeetingRef, agenda_text: str,
                           transcript: str) -> str:
    instructions = (
        "This meeting has already occurred. Produce a Markdown recap with these sections:\n"
        "## TL;DR (3–5 bullets: most important decisions and discussions)\n"
        "## Attendance & housekeeping\n"
        "## Decisions & votes (each with vote count and notable discussion or dissent)\n"
        "## Discussion items (no vote)\n"
        "## Public comment\n"
        "## Notable moments (anything colorful, tense, or unusual)\n"
        "For any section where nothing applies to this meeting, keep the header and write "
        "`_No content._` on a single line beneath it — do not omit sections or leave them empty."
    )

    transcript_block = f"\n===== TRANSCRIPT =====\n{transcript}" if transcript else ""
    transcript_note = "" if transcript else (
        "\nNote: no video transcript is available for this meeting — work from the agenda only.\n"
    )
    members_line = ", ".join(data.members) if data.members else "(not listed)"

    return (
        f"You are summarizing a local government meeting in Boone County, IL "
        f"for a personal briefing.\n"
        f"Government: {jurisdiction_for(body).display_name}\n"
        f"Body: {body.display_name}\n"
        f"Meeting: {ref.title}\n"
        f"Date/Time: {ref.date.isoformat()} {ref.time}  Location: {ref.location or data.location}\n"
        f"Members of record: {members_line}\n\n"
        f"{instructions}\n"
        f"IMPORTANT: Do NOT start with a meeting-title header — the meeting page already "
        f"identifies the meeting. Start directly with the '## TL;DR' section.\n"
        f"Do not invent details not in the source. If the transcript has typos "
        f"(auto-captions), silently correct obvious ones; quote sparingly.\n"
        f"{transcript_note}"
        f"\n===== AGENDA =====\n{agenda_text}\n"
        f"{transcript_block}\n"
    )


def _build_pdf_meeting_prompt(body: Body, meeting_date, agenda: str, minutes: str) -> str:
    return (
        f"You are summarizing a local government meeting in Boone County, IL "
        f"for a personal briefing.\n"
        f"Government: {jurisdiction_for(body).display_name}\n"
        f"Body: {body.display_name}\n"
        f"Date: {meeting_date.isoformat()}\n\n"
        f"Produce a Markdown recap with these sections:\n"
        f"## TL;DR (3–5 bullets)\n"
        f"## Decisions & votes\n"
        f"## Discussion items\n"
        f"## Financial / operational notes\n\n"
        f"For any section where nothing applies to this meeting, keep the header and write "
        f"`_No content._` on a single line beneath it — do not omit sections or leave them empty.\n"
        f"If minutes are missing, work from the agenda only and label the summary '## Agenda preview'.\n"
        f"IMPORTANT: Do NOT start with a meeting-title header — the meeting page already "
        f"identifies the meeting. Start directly with '## TL;DR' (or '## Agenda preview').\n"
        f"Do not invent details.\n"
        f"\n===== AGENDA (PDF text) =====\n{agenda or '[no agenda available]'}\n"
        f"\n===== MINUTES (PDF text) =====\n{minutes or '[no minutes available]'}\n"
    )


def _dataclass_to_dict(obj) -> dict:
    from dataclasses import asdict
    return asdict(obj)


def _call_claude(prompt: str) -> str:
    load_env()
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
