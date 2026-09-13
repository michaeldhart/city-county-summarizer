"""Config, paths, and the canonical jurisdiction + body registries."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
DATA_DIR = REPO_ROOT / "data"
MEETINGS_DIR = DATA_DIR / "meetings"
CACHE_DIR = DATA_DIR / "cache"
MANIFEST_PATH = DATA_DIR / "manifest.json"

BOONE_DILIGENT_BASE = "https://boonecountyil.community.diligentoneplatform.com"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

CLAUDE_MODEL = "claude-sonnet-4-5"


@dataclass(frozen=True)
class Jurisdiction:
    """A government whose bodies we track. Owns the video channel, if any."""
    id: str
    display_name: str
    youtube_channel_id: str | None = None
    youtube_tab: str = "streams"   # county meetings are archived live streams


JURISDICTIONS: tuple[Jurisdiction, ...] = (
    Jurisdiction("boone-county", "Boone County",
                 youtube_channel_id="UCJd8c3sZs98mx9vznx9nsOg"),
    Jurisdiction("bccd", "Boone County Conservation District"),
    Jurisdiction("swcd", "Boone County Soil & Water Conservation District"),
)

JURISDICTIONS_BY_ID: dict[str, Jurisdiction] = {j.id: j for j in JURISDICTIONS}


@dataclass(frozen=True)
class Body:
    id: str                    # short slug (e.g. "board", "cotw-finance")
    display_name: str          # human name shown in SCOPE.md
    jurisdiction_id: str       # key into JURISDICTIONS_BY_ID
    source: str                # manifest id namespace; key into sources.SOURCES
    scope_name: str            # exact string as it appears in SCOPE.md rows
    type_id: int | None = None  # Diligent MeetingTypeId (None for non-diligent sources)


# Canonical registry. `type_id` values from Diligent recon in Aug 2026.
# LEPC and Veteran's Assistance don't appear on Diligent — no id known — they
# stay in scope but won't be matched until we find where their agendas live.
BODIES: tuple[Body, ...] = (
    Body("board", "Boone County Board", "boone-county", "diligent",
         "Boone County Board (12 members, 3 districts)", type_id=22),
    Body("cotw-admin", "COTW – Administrative & Legislative", "boone-county", "diligent",
         "COTW – Administrative & Legislative", type_id=18),
    Body("cotw-finance", "COTW – Finance, Taxation & Salaries", "boone-county", "diligent",
         "COTW – Finance, Taxation & Salaries", type_id=19),
    Body("planning", "Regional Planning Commission", "boone-county", "diligent",
         "Regional Planning Commission", type_id=29),
    Body("zba", "Zoning Board of Appeals", "boone-county", "diligent",
         "Zoning Board of Appeals", type_id=23),
    Body("ag-easement", "Agricultural Conservation Easement Commission", "boone-county", "diligent",
         "Agricultural Conservation Easement & Farmland Protection Commission", type_id=31),
    Body("health", "Board of Health", "boone-county", "diligent",
         "Board of Health", type_id=20),
    Body("lepc", "Local Emergency Planning Committee", "boone-county", "diligent",
         "Local Emergency Planning Committee (LEPC)", type_id=None),
    Body("veterans", "Veteran's Assistance Commission", "boone-county", "diligent",
         "Veteran's Assistance Commission", type_id=None),
    Body("bccd", "Boone County Conservation District", "bccd", "bccd",
         "Boone County Conservation District"),
    Body("swcd", "Soil & Water Conservation District", "swcd", "swcd",
         "Boone County Soil & Water Conservation District"),
)

BODIES_BY_ID: dict[str, Body] = {b.id: b for b in BODIES}


def jurisdiction_for(body: Body) -> Jurisdiction:
    return JURISDICTIONS_BY_ID[body.jurisdiction_id]


def body_for_type_id(source: str, type_id: int) -> Body | None:
    """Diligent MeetingTypeIds are only unique within one tenant — match on both."""
    for b in BODIES:
        if b.source == source and b.type_id == type_id:
            return b
    return None


def load_env() -> None:
    """Load .env from the repo root. Idempotent."""
    load_dotenv(REPO_ROOT / ".env")


def load_scope_statuses() -> dict[str, str]:
    """Parse docs/SCOPE.md and return {scope_name: status}.

    Status is 'tracked' | 'mentioned' | 'excluded' — read from the backtick-wrapped
    value in the second table cell.
    """
    scope_path = DOCS_DIR / "SCOPE.md"
    text = scope_path.read_text()
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name, status_cell = cells[0], cells[1]
        m = re.search(r"`(tracked|mentioned|excluded)`", status_cell)
        if not m:
            continue
        statuses[name] = m.group(1)
    return statuses


def tracked_bodies() -> list[Body]:
    """Bodies currently marked `tracked` in SCOPE.md."""
    statuses = load_scope_statuses()
    return [b for b in BODIES if statuses.get(b.scope_name) == "tracked"]


def is_cancelled(title: str) -> bool:
    return bool(re.match(r"^\s*cancelled", title.strip(), flags=re.IGNORECASE))


def ensure_data_dirs() -> None:
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
