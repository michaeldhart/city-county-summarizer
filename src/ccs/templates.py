"""Markdown format strings for report rendering.

Edit these to change how reports look. All templates use `str.format()` —
placeholders in braces are filled in by `report.py`.

Guideline: keep logic (looping, conditionals) in `report.py`; keep prose,
punctuation, and layout here.
"""
from __future__ import annotations

from datetime import date


# ---- date formatting ----

def fmt_date(d: date) -> str:
    """Short human-readable date, e.g., 'Jun 24, 2026'. Uses `%-d` (Unix only)."""
    return d.strftime("%b %-d, %Y")


# ---- report-level ----

REPORT_HEADER = """# Boone County Government Report: {start} - {end}

Generated: {generated}

Recap window: {recap_start} → {recap_end}
"""

SECTION_SEPARATOR = "\n---\n"

RECAP_HEADING = "## Recap\n"

RECAP_EMPTY = "_No meetings found in the recap window._"

# ---- table of contents ----

TOC_HEADING = "## Contents"
TOC_GROUP_HEADING = "**{group}** ({count} {noun})"
TOC_ENTRY_LINE = "- [{text}](#{anchor})"

# ---- per-entry ----

ENTRY_HEADER = "### {date} — {body}"
ENTRY_SOURCE_LINK = "[Source]({url})"
ENTRY_NO_SUMMARY = "_No summary — meeting has no materials yet._"
ENTRY_SUMMARY_MISSING = "_Summary file missing: {path}_"
