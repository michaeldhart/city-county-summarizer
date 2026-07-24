"""PDF download + text extraction helpers used by BCCD/SWCD and BoardDocs attachments."""
from __future__ import annotations

from pathlib import Path

import pdfplumber
import requests

from .config import HTTP_HEADERS


def download_pdf(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=HTTP_HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 15):
                f.write(chunk)
    return dest


def pdf_to_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n\n".join((p.extract_text() or "") for p in pdf.pages).strip()
