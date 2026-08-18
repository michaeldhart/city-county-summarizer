"""Persistent record of ingested meetings — makes monthly runs incremental."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .config import MANIFEST_PATH


@dataclass
class MeetingRecord:
    id: str                       # globally unique: e.g. "diligent:1622"
    body_id: str
    source: str                   # "diligent" | "bccd" | "swcd"
    date: str                     # ISO YYYY-MM-DD
    title: str
    url: str | None = None
    video_id: str | None = None
    has_transcript: bool = False
    summary_path: str | None = None
    ingested_at: str | None = None


def load() -> dict[str, MeetingRecord]:
    if not MANIFEST_PATH.exists():
        return {}
    raw = json.loads(MANIFEST_PATH.read_text())
    return {mid: MeetingRecord(**m) for mid, m in raw.get("meetings", {}).items()}


def save(records: dict[str, MeetingRecord]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meetings": {mid: asdict(m) for mid, m in records.items()}}
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True))


def upsert(record: MeetingRecord) -> None:
    records = load()
    record.ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records[record.id] = record
    save(records)


def make_id(source: str, key: str) -> str:
    return f"{source}:{key}"


def since(records: dict[str, MeetingRecord], cutoff: date) -> list[MeetingRecord]:
    """Records with date >= cutoff, newest first."""
    return sorted(
        (r for r in records.values() if _parse(r.date) >= cutoff),
        key=lambda r: r.date, reverse=True,
    )


def _parse(iso: str) -> date:
    return datetime.strptime(iso, "%Y-%m-%d").date()
