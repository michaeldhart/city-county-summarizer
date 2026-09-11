"""Generate the Jekyll site's `_bodies`/`_meetings` collections from the manifest.

Fully regenerates both collections on every run — cheap, since it's just
writing markdown files with YAML front matter, and it avoids having to diff
against or prune stale docs.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import manifest
from .config import REPO_ROOT, Body, tracked_bodies
from .report import clean_meeting_title

WEBSITE_DIR = REPO_ROOT / "website"
BODIES_DIR = WEBSITE_DIR / "_bodies"
MEETINGS_DIR = WEBSITE_DIR / "_meetings"


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
    front_matter = {
        "title": body.display_name,
        "body_id": body.id,
        "permalink": f"/bodies/{body.id}/",
    }
    _write_doc(BODIES_DIR / f"{body.id}.md", front_matter, "")


def _write_meeting_doc(record: manifest.MeetingRecord) -> None:
    slug = record.id.replace(":", "-")
    front_matter = {
        "title": clean_meeting_title(record.title) or record.body_id,
        "body_id": record.body_id,
        "date": record.date,
        "permalink": f"/bodies/{record.body_id}/meetings/{slug}/",
    }
    if record.url:
        front_matter["source_url"] = record.url
    _write_doc(MEETINGS_DIR / f"{slug}.md", front_matter, _meeting_body_content(record))


def _meeting_body_content(record: manifest.MeetingRecord) -> str:
    """The meeting page's markdown body: the cached per-meeting summary.

    Strips a leading '# ...' title header if present (legacy summaries wrote
    one; current prompts skip it) since the page's own layout already
    renders the title as an <h1>.
    """
    if not record.summary_path:
        return "_No summary — meeting has no materials yet._\n"
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
