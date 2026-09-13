"""Source registry: maps a manifest id namespace to the client that serves it.

`Body.source` is the namespace in a meeting id (`diligent:1622`, `bccd:20260420`).
It's deliberately separate from the client module — Boone County and District 100
are both Diligent tenants, but their numeric meeting ids overlap, so each tenant
needs its own namespace pointing at its own base URL.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Union

from . import bccd, bpd, swcd
from .config import BOONE_DILIGENT_BASE, D100_DILIGENT_BASE


@dataclass(frozen=True)
class DiligentSource:
    base: str


@dataclass(frozen=True)
class PdfIndexSource:
    """A site publishing a flat index of per-meeting agenda/minutes documents.

    `list_meetings` returns objects exposing `.date`, `.agenda_url` and
    `.minutes_url`, plus `.key` (the manifest id suffix, unique within the
    source) and `.name` (the meeting's own name, or "" to fall back to the
    body's display name).
    """
    list_meetings: Callable[[], List]


Source = Union[DiligentSource, PdfIndexSource]

SOURCES: dict[str, Source] = {
    "diligent": DiligentSource(BOONE_DILIGENT_BASE),
    "d100": DiligentSource(D100_DILIGENT_BASE),
    "bccd": PdfIndexSource(bccd.list_meetings),
    "swcd": PdfIndexSource(swcd.list_meetings),
    "bpd": PdfIndexSource(bpd.list_meetings),
}


def diligent_base(source: str) -> str:
    src = SOURCES.get(source)
    if not isinstance(src, DiligentSource):
        raise ValueError(f"source '{source}' is not a Diligent tenant")
    return src.base


def pdf_index_lister(source: str) -> Callable[[], List]:
    src = SOURCES.get(source)
    if not isinstance(src, PdfIndexSource):
        raise ValueError(f"source '{source}' is not a PDF-index site")
    return src.list_meetings
