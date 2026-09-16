"""Ingest a single meeting end-to-end: pull sources, call Claude, save summary."""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

from . import diligent, manifest, pdftext, resources, youtube
from .config import (
    CLAUDE_MODEL,
    MEETINGS_DIR,
    REPO_ROOT,
    Body,
    ensure_data_dirs,
    jurisdiction_for,
    load_env,
)


# Claude's context is 200K tokens. Budget in characters per source rather than
# trusting a token estimate: OCR'd scans tokenize far worse than clean text —
# broken words push Belvidere's packets to ~2 chars/token against the usual ~4,
# so one 559K-char packet came to 286K tokens on its own. Minutes and transcript
# get the smaller cuts because they're the actual record; a packet is mostly
# supporting attachments behind the agenda, which sits at the front.
MAX_AGENDA_CHARS = 120_000
MAX_MINUTES_CHARS = 60_000
MAX_TRANSCRIPT_CHARS = 120_000


def _clip(text: str, limit: int, what: str) -> str:
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n\n[... {what} truncated: {len(text):,} chars total, first {limit:,} shown ...]"
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

    # Prefer the tenant's own video link; only guess from titles when it's empty.
    video_id = diligent.get_video_id(base, ref.id)
    if video_id is None and videos is not None:
        match = youtube.find_video(videos, ref.date, body.id)
        if match is not None:
            video_id = match.video_id

    transcript = ""
    if video_id is not None:
        vtt = youtube.download_captions(video_id, outdir)
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
        resources=resources.for_diligent(
            base, ref.id, agenda_doc.html if agenda_doc else "",
            video_id, bool(transcript),
        ),
    )


def ingest_pdf_meeting(source: str, meeting, body: Body,
                       videos: list[youtube.YouTubeVideo] | None = None) -> manifest.MeetingRecord:
    """Recap for a site that posts agenda/minutes PDFs: download, extract, summarize.

    `meeting` is any object exposing `.date`, `.key`, `.name`, `.agenda_url`
    and `.minutes_url` — see sources.PdfIndexSource.
    """
    meeting_id = manifest.make_id(source, meeting.key)
    outdir = _meeting_dir(meeting_id)

    agenda_text = _download_and_extract(meeting.agenda_url, outdir / "agenda.pdf", outdir / "agenda.txt")
    minutes_text = _download_and_extract(meeting.minutes_url, outdir / "minutes.pdf", outdir / "minutes.txt")

    # Belvidere's Committee of the Whole never publishes minutes, so for those
    # meetings the transcript is the only record of what was actually said.
    transcript = ""
    video_id: str | None = None
    if videos is not None:
        match = youtube.find_video(videos, meeting.date, body.id)
        if match is not None:
            video_id = match.video_id
            vtt = youtube.download_captions(video_id, outdir)
            if vtt is not None:
                transcript = youtube.vtt_to_text(vtt)
                (outdir / "transcript.txt").write_text(transcript)

    prompt = _build_pdf_meeting_prompt(body, meeting.date, agenda_text, minutes_text, transcript)
    summary = _call_claude(prompt)
    (outdir / "summary.md").write_text(summary)

    return manifest.MeetingRecord(
        id=meeting_id,
        body_id=body.id,
        source=source,
        date=meeting.date.isoformat(),
        title=meeting.name or body.display_name,
        url=meeting.agenda_url or meeting.minutes_url,
        video_id=video_id,
        has_transcript=bool(transcript),
        summary_path=str((outdir / "summary.md").relative_to(REPO_ROOT)),
        resources=resources.for_pdf_meeting(
            meeting.agenda_url, meeting.minutes_url, video_id, bool(transcript),
        ),
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
    # Without a transcript there is no record of what was said — only what was
    # scheduled. Asking for votes and attendance then just yields a page of
    # "_No content._", which reads as a failed recap rather than an agenda.
    if transcript:
        instructions = (
            "This meeting has already occurred. Produce a Markdown recap with these sections:\n"
            "## The lede (3–5 bullets: most important decisions and discussions)\n"
            "## Attendance & housekeeping\n"
            "## Decisions & votes (each with vote count and notable discussion or dissent)\n"
            "## Discussion items (no vote)\n"
            "## Public comment\n"
            "## Notable moments (anything colorful, tense, or unusual)\n"
            "For any section where nothing applies to this meeting, keep the header and write "
            "`_No content._` on a single line beneath it — do not omit sections or leave them "
            "empty.\nStart directly with the '## The lede' section."
        )
    else:
        instructions = (
            "Only the agenda is available for this meeting — there is no transcript and no "
            "minutes, so there is no record of what was actually said or decided.\n"
            "Produce a Markdown agenda preview with these sections:\n"
            "## Agenda preview (3–5 bullets: what this body is set to take up)\n"
            "## Items for decision\n"
            "## Other business\n"
            "Describe what is scheduled, never what was decided. Do not write that anything "
            "was approved, passed, or discussed.\n"
            "Start directly with the '## Agenda preview' section."
        )

    transcript_block = (
        f"\n===== TRANSCRIPT =====\n{_clip(transcript, MAX_TRANSCRIPT_CHARS, 'transcript')}"
        if transcript else ""
    )
    transcript_note = "" if transcript else (
        "\nNote: no video transcript is available for this meeting — work from the agenda only.\n"
    )
    members_line = ", ".join(data.members) if data.members else "(not listed)"

    return (
        f"You are filing a dispatch on a local government meeting in Boone County, "
        f"IL for The Belvidere Wire, which publishes a recap of every public "
        f"meeting in the county.\n"
        f"Government: {jurisdiction_for(body).display_name}\n"
        f"Body: {body.display_name}\n"
        f"Meeting: {ref.title}\n"
        f"Date/Time: {ref.date.isoformat()} {ref.time}  Location: {ref.location or data.location}\n"
        f"Members of record: {members_line}\n\n"
        f"{instructions}\n"
        f"IMPORTANT: Do NOT start with a meeting-title header — the meeting page already "
        f"identifies the meeting.\n"
        f"Report what happened; do not characterize motives, assign praise or blame, or read\n"
        f"significance into a vote. Record the count and the discussion as they occurred.\n"
        f"Prefer plain words to civic jargon — \"the board agreed to buy 34 acres\", not\n"
        f"\"authorized acquisition of a parcel\" — since this is read by residents, not clerks.\n"
        "Do not invent details not in the source. If the transcript has typos "
        f"(auto-captions), silently correct obvious ones; quote sparingly.\n"
        f"{transcript_note}"
        f"\n===== AGENDA =====\n{_clip(agenda_text, MAX_AGENDA_CHARS, 'agenda')}\n"
        f"{transcript_block}\n"
    )


def _build_pdf_meeting_prompt(body: Body, meeting_date, agenda: str, minutes: str,
                              transcript: str = "") -> str:
    has_record = bool(minutes.strip() or transcript.strip())
    sections = (
        "## The lede (3–5 bullets)\n"
        "## Decisions & votes\n"
        "## Discussion items\n"
        "## Financial / operational notes\n"
    )
    if transcript:
        sections += "## Public comment\n## Notable moments\n"

    if has_record:
        mode = (
            "Start directly with the '## The lede' section.\n"
        )
    else:
        mode = (
            "Only the agenda is available — no minutes and no transcript. Label the "
            "summary '## Agenda preview' and start directly with that header, and do "
            "not describe anything as having been decided.\n"
        )

    transcript_block = (
        f"\n===== TRANSCRIPT =====\n{_clip(transcript, MAX_TRANSCRIPT_CHARS, 'transcript')}"
        if transcript else ""
    )

    return (
        f"You are filing a dispatch on a local government meeting in Boone County, "
        f"IL for The Belvidere Wire, which publishes a recap of every public "
        f"meeting in the county.\n"
        f"Government: {jurisdiction_for(body).display_name}\n"
        f"Body: {body.display_name}\n"
        f"Date: {meeting_date.isoformat()}\n\n"
        f"Produce a Markdown recap with these sections:\n"
        f"{sections}\n"
        f"For any section where nothing applies to this meeting, keep the header and write "
        f"`_No content._` on a single line beneath it — do not omit sections or leave them empty.\n"
        f"A source marked truncated is cut for length; summarize what is there and do "
        f"not guess at the rest.\n"
        f"{mode}"
        f"IMPORTANT: Do NOT start with a meeting-title header — the meeting page already "
        f"identifies the meeting.\n"
        f"Report what happened; do not characterize motives, assign praise or blame, or read\n"
        f"significance into a vote. Record the count and the discussion as they occurred.\n"
        f"Prefer plain words to civic jargon — \"the board agreed to buy 34 acres\", not\n"
        f"\"authorized acquisition of a parcel\" — since this is read by residents, not clerks.\n"
        "Do not invent details. If the transcript has typos (auto-captions), silently "
        f"correct obvious ones; quote sparingly.\n"
        f"\n===== AGENDA (PDF text) =====\n"
        f"{_clip(agenda, MAX_AGENDA_CHARS, 'agenda') or '[no agenda available]'}\n"
        f"\n===== MINUTES (PDF text) =====\n"
        f"{_clip(minutes, MAX_MINUTES_CHARS, 'minutes') or '[no minutes available]'}\n"
        f"{transcript_block}\n"
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
