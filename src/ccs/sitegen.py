"""Generate the Jekyll site's `_bodies`/`_meetings` collections from the manifest.

Fully regenerates both collections on every run — cheap, since it's just
writing markdown files with YAML front matter, and it avoids having to diff
against or prune stale docs.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from . import manifest
from .config import (
    BODY_ORDER,
    JURISDICTION_ORDER,
    REPO_ROOT,
    Body,
    about_url_for,
    jurisdiction_for,
    tracked_bodies,
)
from .report import clean_meeting_title

WEBSITE_DIR = REPO_ROOT / "website"
BODIES_DIR = WEBSITE_DIR / "_bodies"
MEETINGS_DIR = WEBSITE_DIR / "_meetings"


def meeting_slug(meeting_id: str) -> str:
    return meeting_id.replace(":", "-")


def body_permalink(body_id: str) -> str:
    return f"/bodies/{body_id}/"


def meeting_permalink(body_id: str, meeting_id: str) -> str:
    """The site path for one dispatch.

    Defined here rather than inline because the front page links to dispatches
    too, and two copies of a URL shape drift the first time one of them changes.
    """
    return f"/bodies/{body_id}/meetings/{meeting_slug(meeting_id)}/"


def build_site_content() -> tuple[int, int]:
    """Write `_bodies/*.md` and `_meetings/*.md`. Returns (body_count, meeting_count)."""
    bodies = tracked_bodies()
    tracked_ids = {b.id for b in bodies}
    records = manifest.load()

    _clear_dir(BODIES_DIR)
    _clear_dir(MEETINGS_DIR)

    for body in bodies:
        _write_body_doc(body)

    meeting_count = 0
    for record in records.values():
        if record.body_id not in tracked_ids:
            continue
        _write_meeting_doc(record)
        meeting_count += 1

    return len(bodies), meeting_count


def _clear_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.md"):
        f.unlink()


def _write_body_doc(body: Body) -> None:
    jurisdiction = jurisdiction_for(body)
    front_matter = {
        "title": body.display_name,
        "body_id": body.id,
        "jurisdiction": jurisdiction.display_name,
        "jurisdiction_id": jurisdiction.id,
        "about_url": about_url_for(jurisdiction.id),
        # Liquid can't sort groups by an external order, so bake one in: the
        # index sorts on this and starts a new heading when jurisdiction changes.
        "sort_key": "{:02d}-{:03d}".format(
            JURISDICTION_ORDER[jurisdiction.id], BODY_ORDER[body.id]
        ),
        "permalink": body_permalink(body.id),
    }
    _write_doc(BODIES_DIR / f"{body.id}.md", front_matter, "")


def _write_meeting_doc(record: manifest.MeetingRecord) -> None:
    slug = meeting_slug(record.id)
    front_matter = {
        "title": clean_meeting_title(record.title) or record.body_id,
        "body_id": record.body_id,
        "date": record.date,
        "permalink": meeting_permalink(record.body_id, record.id),
    }
    if record.url:
        front_matter["source_url"] = record.url
    # The byline on the meeting page names the sources this dispatch was
    # actually written from. Agenda and minutes it can infer from `resources`,
    # but a video resource is only a link we publish — it says nothing about
    # whether captions existed to read. Carry the transcript flag through so
    # the byline can only claim the video when the transcript was really used.
    if record.has_transcript:
        front_matter["has_transcript"] = True
    if record.resources:
        front_matter["resources"] = [asdict(r) for r in record.resources]
    _write_doc(MEETINGS_DIR / f"{slug}.md", front_matter, _meeting_body_content(record))


def _meeting_body_content(record: manifest.MeetingRecord) -> str:
    """The dispatch's markdown body: the cached per-meeting summary.

    Strips a leading '# ...' title header if present (legacy summaries wrote
    one; current prompts skip it) since the page's own layout already
    renders the title as an <h1>.
    """
    if not record.summary_path:
        return "_Nothing filed — this meeting has published no materials yet._\n"
    summary_path = REPO_ROOT / record.summary_path
    if not summary_path.exists():
        return f"_Summary file missing: {record.summary_path}_\n"
    lines = summary_path.read_text().splitlines()
    if lines and lines[0].lstrip().startswith("# ") and not lines[0].lstrip().startswith("## "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).rstrip() + "\n"


def _write_doc(path: Path, front_matter: dict, body: str) -> None:
    fm = yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n\n{body}")
