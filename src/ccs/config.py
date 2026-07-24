"""Config, paths, and the canonical body registry."""
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

BOARDDOCS_BASE = "https://go.boarddocs.com/il/boone/Board.nsf"
BOARDDOCS_COMMITTEE_ID = "AAL6YS173AC9"
YOUTUBE_CHANNEL_ID = "UCJd8c3sZs98mx9vznx9nsOg"

# Realistic browser headers — BoardDocs' CloudFront rejects bare curl.
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
BOARDDOCS_HEADERS = {
    **HTTP_HEADERS,
    "Origin": "https://go.boarddocs.com",
    "Referer": f"{BOARDDOCS_BASE}/Public",
    "Content-Type": "application/x-www-form-urlencoded",
}

CLAUDE_MODEL = "claude-sonnet-4-5"


@dataclass(frozen=True)
class Body:
    id: str                    # short slug (e.g. "board", "cotw-finance")
    display_name: str          # human name shown in SCOPE.md
    source: str                # "boarddocs" | "bccd" | "swcd"
    scope_name: str            # exact string as it appears in SCOPE.md rows
    title_patterns: tuple[str, ...] = ()  # regex patterns matching BoardDocs meeting titles


# Canonical registry. `title_patterns` come from real observed titles in the spike.
# Sub-body meetings on BoardDocs share the same committee_id as Board meetings —
# we distinguish them by matching the meeting title.
BODIES: tuple[Body, ...] = (
    Body("board", "Boone County Board", "boarddocs",
         "Boone County Board (12 members, 3 districts)",
         (r"^boone county board meeting$",)),
    Body("cotw-admin", "COTW – Administrative & Legislative", "boarddocs",
         "COTW – Administrative & Legislative",
         (r"committee of the whole.*admin",)),
    Body("cotw-finance", "COTW – Finance, Taxation & Salaries", "boarddocs",
         "COTW – Finance, Taxation & Salaries",
         (r"committee of the whole.*finance",)),
    Body("planning", "Regional Planning Commission", "boarddocs",
         "Regional Planning Commission",
         (r"regional planning commission",)),
    Body("zba", "Zoning Board of Appeals", "boarddocs",
         "Zoning Board of Appeals",
         (r"zoning board of appeals",)),
    Body("ag-easement", "Agricultural Conservation Easement Commission", "boarddocs",
         "Agricultural Conservation Easement & Farmland Protection Commission",
         (r"agricultural conservation easement", r"farmland protection")),
    Body("health", "Board of Health", "boarddocs",
         "Board of Health",
         (r"board of health",)),
    Body("lepc", "Local Emergency Planning Committee", "boarddocs",
         "Local Emergency Planning Committee (LEPC)",
         (r"local emergency planning", r"\blepc\b")),
    Body("veterans", "Veteran's Assistance Commission", "boarddocs",
         "Veteran's Assistance Commission",
         (r"veteran'?s? assistance",)),
    Body("bccd", "Boone County Conservation District", "bccd",
         "Boone County Conservation District"),
    Body("swcd", "Soil & Water Conservation District", "swcd",
         "Boone County Soil & Water Conservation District"),
)

BODIES_BY_ID: dict[str, Body] = {b.id: b for b in BODIES}


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


def body_for_title(title: str) -> Body | None:
    """Match a BoardDocs meeting title to a body via its regex patterns.

    Strips 'CANCELLED' / 'CANCELLED/RESCHEDULED' prefixes first.
    """
    cleaned = re.sub(
        r"^\s*(cancelled(?:\s*/\s*rescheduled)?)\s*",
        "",
        title.strip(),
        flags=re.IGNORECASE,
    ).strip().lower()
    for body in BODIES:
        if body.source != "boarddocs":
            continue
        for pat in body.title_patterns:
            if re.search(pat, cleaned, flags=re.IGNORECASE):
                return body
    return None


def is_cancelled(title: str) -> bool:
    return bool(re.match(r"^\s*cancelled", title.strip(), flags=re.IGNORECASE))


def ensure_data_dirs() -> None:
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
