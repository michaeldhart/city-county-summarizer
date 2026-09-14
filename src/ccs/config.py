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
D100_DILIGENT_BASE = "https://district100.community.highbond.com"

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


# Order here is the order jurisdictions appear on the site.
JURISDICTIONS: tuple[Jurisdiction, ...] = (
    Jurisdiction("boone-county", "Boone County",
                 youtube_channel_id="UCJd8c3sZs98mx9vznx9nsOg"),
    Jurisdiction("belvidere", "City of Belvidere",
                 youtube_channel_id="UCotr1ZcGCImOF33lrGH2x3A", youtube_tab="videos"),
    Jurisdiction("d100", "Belvidere Community Unit School District 100",
                 youtube_channel_id="UCS3r7OLVDHpE9DroeciYCow", youtube_tab="videos"),
    Jurisdiction("bpd", "Belvidere Township Park District"),
    Jurisdiction("bccd", "Boone County Conservation District"),
    Jurisdiction("swcd", "Boone County Soil & Water Conservation District"),
)

JURISDICTION_ORDER: dict = {j.id: i for i, j in enumerate(JURISDICTIONS)}
BODY_ORDER: dict = {}   # filled below, once BODIES exists

JURISDICTIONS_BY_ID: dict[str, Jurisdiction] = {j.id: j for j in JURISDICTIONS}


@dataclass(frozen=True)
class Body:
    id: str                    # short slug (e.g. "board", "cotw-finance")
    display_name: str          # human name shown in SCOPE.md
    jurisdiction_id: str       # key into JURISDICTIONS_BY_ID
    source: str                # manifest id namespace; key into sources.SOURCES
    scope_name: str            # exact string as it appears in SCOPE.md rows
    type_ids: tuple = ()       # Diligent MeetingTypeIds; empty for non-Diligent sources


# Canonical registry. `type_id` values from Diligent recon in Aug 2026.
# LEPC and Veteran's Assistance don't appear on Diligent — no id known — they
# stay in scope but won't be matched until we find where their agendas live.
BODIES: tuple[Body, ...] = (
    Body("board", "Boone County Board", "boone-county", "diligent",
         "Boone County Board (12 members, 3 districts)", type_ids=(22,)),
    Body("cotw-admin", "COTW – Administrative & Legislative", "boone-county", "diligent",
         "COTW – Administrative & Legislative", type_ids=(18,)),
    Body("cotw-finance", "COTW – Finance, Taxation & Salaries", "boone-county", "diligent",
         "COTW – Finance, Taxation & Salaries", type_ids=(19,)),
    Body("planning", "Regional Planning Commission", "boone-county", "diligent",
         "Regional Planning Commission", type_ids=(29,)),
    Body("zba", "Zoning Board of Appeals", "boone-county", "diligent",
         "Zoning Board of Appeals", type_ids=(23,)),
    Body("ag-easement", "Agricultural Conservation Easement Commission", "boone-county", "diligent",
         "Agricultural Conservation Easement & Farmland Protection Commission", type_ids=(31,)),
    Body("health", "Board of Health", "boone-county", "diligent",
         "Board of Health", type_ids=(20,)),
    Body("lepc", "Local Emergency Planning Committee", "boone-county", "diligent",
         "Local Emergency Planning Committee (LEPC)"),
    Body("veterans", "Veteran's Assistance Commission", "boone-county", "diligent",
         "Veteran's Assistance Commission"),
    Body("bccd", "Boone County Conservation District", "bccd", "bccd",
         "Boone County Conservation District"),
    Body("swcd", "Soil & Water Conservation District", "swcd", "swcd",
         "Boone County Soil & Water Conservation District"),
    # District 100 runs the same Diligent product as the county on its own
    # tenant. Workshops (158), retreats (150), town halls (153), hearings (157)
    # and special meetings (156) are all the Board of Education meeting under a
    # different label, so they share one body rather than fragmenting the page.
    Body("d100-board", "Board of Education", "d100", "d100",
         "BCUSD 100 Board of Education", type_ids=(15, 150, 153, 156, 157, 158)),
    Body("d100-business", "Business Services Committee", "d100", "d100",
         "BCUSD 100 Business Services Committee", type_ids=(10,)),
    Body("d100-education", "Educational Services Committee", "d100", "d100",
         "BCUSD 100 Educational Services Committee", type_ids=(50,)),
    Body("d100-policy", "Policy & Personnel Committee", "d100", "d100",
         "BCUSD 100 Policy & Personnel Committee", type_ids=(51,)),
    Body("d100-ptac", "Parent Teacher Advisory Committee", "d100", "d100",
         "BCUSD 100 Parent Teacher Advisory Committee", type_ids=(16,)),
    Body("bpd-board", "Board of Commissioners", "bpd", "bpd",
         "Belvidere Township Park District Board"),
    # One WordPress site serves all five city bodies, so they share a source and
    # their meetings carry their own body_id. The Planning & Zoning Commission
    # also sits as the Zoning Board of Appeals — there is no separate ZBA.
    Body("belvidere-council", "City Council", "belvidere", "belvidere",
         "Belvidere City Council"),
    Body("belvidere-cow", "Committee of the Whole", "belvidere", "belvidere",
         "Belvidere Committee of the Whole"),
    Body("belvidere-pzc", "Planning & Zoning Commission", "belvidere", "belvidere",
         "Belvidere Planning & Zoning Commission"),
    Body("belvidere-hpc", "Historic Preservation Commission", "belvidere", "belvidere",
         "Belvidere Historic Preservation Commission"),
    Body("belvidere-fpc", "Board of Fire & Police Commissioners", "belvidere", "belvidere",
         "Belvidere Board of Fire & Police Commissioners"),
)

BODIES_BY_ID: dict[str, Body] = {b.id: b for b in BODIES}
BODY_ORDER.update({b.id: i for i, b in enumerate(BODIES)})


# The conservation districts are one-body governments already covered inside the
# county's About page; they don't need pages of their own.
ABOUT_PAGE_FOR: dict = {"bccd": "boone-county", "swcd": "boone-county"}


def jurisdiction_for(body: Body) -> Jurisdiction:
    return JURISDICTIONS_BY_ID[body.jurisdiction_id]


def about_url_for(jurisdiction_id: str) -> str:
    return "/about/{}/".format(ABOUT_PAGE_FOR.get(jurisdiction_id, jurisdiction_id))


def body_for_type_id(source: str, type_id: int) -> Body | None:
    """Diligent MeetingTypeIds are only unique within one tenant — match on both.

    A body can claim several type ids: District 100 files workshops, retreats,
    town halls and hearings as their own types, but they're all meetings of the
    same Board of Education.
    """
    for b in BODIES:
        if b.source == source and type_id in b.type_ids:
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
