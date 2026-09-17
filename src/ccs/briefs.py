"""Front-page briefs: one to three short items per meeting, written from its dispatch.

A brief is a self-contained news item — a headline, one paragraph, and a pointer
back to the dispatch it came from. Briefs are what the front page is assembled
from; the dispatch itself is unchanged by this step.

Generation is separate from ingestion on purpose. `ccs sync` is the expensive
step and produces the durable record; this reads that record's finished summary
and costs about a cent per meeting, so it can be re-run over the whole archive
after a prompt change without much thought.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from . import manifest
from .config import (
    BRIEF_MAX_PER_MEETING,
    CLAUDE_MODEL,
    MEETINGS_DIR,
    REPO_ROOT,
    jurisdiction_for,
    load_env,
    tracked_bodies,
)

KINDS = ("civic", "significant", "summary")

# Ranking leans on this before any model sees the candidates: a civic brief from
# a dull meeting should still outrank a procedural one from an interesting meeting.
KIND_RANK = {"civic": 0, "significant": 1, "summary": 2}


@dataclass
class Brief:
    """One front-page item.

    `id` is stable across regeneration only while the headline is: it is a hash
    of the headline, not a position in the list. A positional id would silently
    re-point a pin at a different brief the next time a meeting was re-briefed;
    a content hash dangles loudly instead, which is the failure we can warn about.

    `pinned` is never written by Claude. It is set at load time from docs/PINS.md,
    which is tracked in git — data/ is regenerable cache, and an editorial
    decision has to outlive `rm -rf data/`.
    """
    id: str
    headline: str
    body: str
    kind: str
    score: int
    meeting_id: str
    pinned: bool = False


@dataclass
class BriefSet:
    """Everything stored beside a meeting's summary, plus what it was made from."""
    meeting_id: str
    summary_fingerprint: str
    generated_at: str
    briefs: list = field(default_factory=list)


def path_for(record: manifest.MeetingRecord) -> Path:
    """briefs.json beside the summary it was written from.

    Derived from summary_path rather than rebuilt from the record id: the data
    directory names and the manifest ids don't use the same separators, and
    there is no reason for a second place to know that.
    """
    if record.summary_path:
        return (REPO_ROOT / record.summary_path).parent / "briefs.json"
    return MEETINGS_DIR / record.id.replace(":", "-") / "briefs.json"


def fingerprint(summary_text: str) -> str:
    return hashlib.sha256(summary_text.encode("utf-8")).hexdigest()[:16]


def load(record: manifest.MeetingRecord) -> BriefSet | None:
    p = path_for(record)
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    return BriefSet(
        meeting_id=raw["meeting_id"],
        summary_fingerprint=raw["summary_fingerprint"],
        generated_at=raw["generated_at"],
        briefs=[Brief(**b) for b in raw.get("briefs", [])],
    )


def write(record: manifest.MeetingRecord, briefs: list, summary_fingerprint: str) -> Path:
    p = path_for(record)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = BriefSet(
        meeting_id=record.id,
        summary_fingerprint=summary_fingerprint,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        briefs=briefs,
    )
    p.write_text(json.dumps(asdict(payload), indent=2, ensure_ascii=False))
    return p


def is_current(record: manifest.MeetingRecord, summary_text: str) -> bool:
    """True when briefs already exist for exactly this summary.

    Lets `ccs brief` be re-run over the whole archive for free, while a meeting
    whose summary was rewritten (prompt tuning, a re-ingest) is picked up again.
    """
    existing = load(record)
    return existing is not None and existing.summary_fingerprint == fingerprint(summary_text)


def summary_text_for(record: manifest.MeetingRecord) -> str | None:
    if not record.summary_path:
        return None
    p = REPO_ROOT / record.summary_path
    return p.read_text() if p.exists() else None


def generate(record: manifest.MeetingRecord) -> list:
    """One Claude call. Returns the briefs; the caller decides whether to store them."""
    summary = summary_text_for(record)
    if summary is None:
        return []
    body = _body_for(record)
    prompt = _build_prompt(record, body, summary)
    raw = _call_claude(prompt)
    return _parse(raw, record)


def _body_for(record: manifest.MeetingRecord):
    return next((b for b in tracked_bodies() if b.id == record.body_id), None)


def is_agenda_preview(summary: str) -> bool:
    """A dispatch written from an agenda alone, with no record of what happened."""
    return "## Agenda preview" in summary[:400]


def _build_prompt(record: manifest.MeetingRecord, body, summary: str) -> str:
    government = jurisdiction_for(body).display_name if body else "Boone County"
    body_name = body.display_name if body else record.body_id
    preview_note = (
        "\nTHIS DISPATCH IS AN AGENDA PREVIEW. The meeting date above has passed, but\n"
        "the only source is the agenda — nothing records what was actually decided.\n"
        "Write about what the body was SET TO take up, in the past tense ('was\n"
        "scheduled to vote on'), and never state that anything was decided, approved\n"
        "or rejected.\n"
        "Keep the HEADLINE nominal rather than tensed: name the subject, and let the\n"
        "body carry the tense. 'Subdivision ordinance changes under review', not\n"
        "'Subdivision ordinance changes were set for review'. A headline built around\n"
        "'was set to' or 'were scheduled to' reads as broken news rather than news.\n"
        if is_agenda_preview(summary) else ""
    )
    return f"""You are writing front-page briefs for The Belvidere Wire, which publishes a
dispatch on every public meeting of local government in Boone County, Illinois.

A brief is a short, self-contained news item: a headline and a single paragraph,
printed on the front page to send a reader to the full dispatch. You are writing
these from the dispatch below.

Government: {government}
Body: {body_name}
Meeting date: {record.date}

Write between 1 and {BRIEF_MAX_PER_MEETING} briefs for this meeting. Choose them in this order:

1. kind "civic" — up to 3. Anything a resident of this county would actually want
   to know about. This publication exists to make local government visible and to
   give people a reason and a way to take part, so these are the briefs that matter
   most. What qualifies:
     - residents turned out over it: people spoke at public comment, filled the
       room, organized, or petitioned. Public turnout is the single strongest
       signal that something belongs on the front page
     - it is a live controversy the public is already engaged in, or one a
       resident could still influence: an upcoming vote, an open comment period,
       a hearing with a date, a vacancy accepting applications
     - it touches residents' money, property, safety, or public services
     - it is contested, unusual, or reverses a previous position
     - it commits public money at a scale worth noticing
     - it is something a resident would have no other way to find out

2. kind "significant" — up to 2. The most important things that happened at this
   meeting, when they don't rise to the above. Real decisions and real spending,
   reported plainly.

3. kind "summary" — exactly 1, and only when nothing above applies. A plain account
   of what this body did at this meeting. Use this for genuinely routine meetings
   rather than inflating a consent agenda into news.

You may mix kinds up to a total of {BRIEF_MAX_PER_MEETING} — for example one "civic" and two
"significant". Always write at least one brief. Never write more than {BRIEF_MAX_PER_MEETING}.

Routine business scores low and should usually not become a "civic" brief at all:
approving minutes, accepting reports, consent agendas, procedural motions, and
anything whose only content is that a meeting took place.

NEVER quote the meeting verbatim, and never put words in quotation marks and
attribute them to a person. Most of these dispatches are written partly from
automatic video captions that garble names and phrasing, and a quotation is a
stronger claim than that source can carry. Write every brief in your own words.
A brief may be read days or weeks after the meeting it describes, so it must not
go stale. Never write in the future tense about a date that has already passed:
"will hold a hearing on September 8" is wrong once September 8 is gone. Write
what happened, or what a body was scheduled to do, in the past tense, and keep
the future tense for dates that are genuinely still ahead.

Do not invent anything that is not in the dispatch below.

{preview_note}
Each brief has these fields:
  headline  Sentence case, present tense, no leading articles, at most 9 words.
            "County board delays vote on solar ordinance" — not "The County Board
            Has Delayed A Vote".
  body      40-60 words, one paragraph, plain words over civic jargon. This is a
            hard limit, not a target: these are printed in narrow columns and a
            75-word brief breaks the page. Cut detail rather than run over. It
            must still stand on its own for a reader who never clicks through.
  kind      "civic", "significant", or "summary" as defined above.
  score     0-100. How strongly this item helps a resident see what their local
            government is doing, or act on it. Use the whole range and anchor on
            these:
              90-100  a contested decision with public turnout, or one that
                      changes what a resident pays, owns, or is allowed to do
              70-89   real money or a real policy change, still open to influence
              50-69   a decision worth knowing about, largely settled
              30-49   routine but real business
              0-29    procedural: minutes, reports, consent agendas
            Do not bunch everything in the middle. If residents packed a room to
            object to something, that is a 90, not a 70.

Return ONLY a JSON array of objects with exactly those four keys. No prose, no
code fence, no trailing commentary.

===== DISPATCH =====
{summary}
"""


def _parse(raw: str, record: manifest.MeetingRecord) -> list:
    """Parse the model's JSON, tolerating a code fence, and drop anything malformed.

    A bad brief is discarded rather than raising: one unusable item out of three
    shouldn't cost the whole meeting a re-run, and the count is reported so a
    systematic problem is visible rather than silent.
    """
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []

    out = []
    for item in items[:BRIEF_MAX_PER_MEETING]:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline", "")).strip()
        body_text = str(item.get("body", "")).strip()
        kind = str(item.get("kind", "")).strip().lower()
        if not headline or not body_text or kind not in KINDS:
            continue
        try:
            score = max(0, min(100, int(item.get("score", 0))))
        except (TypeError, ValueError):
            score = 0
        out.append(Brief(
            id=brief_id(record.id, headline),
            headline=headline,
            body=body_text,
            kind=kind,
            score=score,
            meeting_id=record.id,
        ))
    return out


def brief_id(meeting_id: str, headline: str) -> str:
    digest = hashlib.sha256(headline.encode("utf-8")).hexdigest()[:4]
    return f"{meeting_id}#{digest}"


def _call_claude(prompt: str) -> str:
    load_env()
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
