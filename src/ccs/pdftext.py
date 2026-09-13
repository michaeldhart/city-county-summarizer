"""PDF download + text extraction, with an OCR fallback for scanned documents.

Belvidere's copiers (Canon MF720C, Konica bizhub) emit pure-raster PDFs with no
font resources — pdfplumber returns nothing for them. Anything thinner than
MIN_CHARS_PER_PAGE gets routed through ocrmypdf, which writes a searchable copy
alongside the original so re-runs skip the work.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import pdfplumber
import requests

from .config import HTTP_HEADERS

MIN_CHARS_PER_PAGE = 150


def download_pdf(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=HTTP_HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 15):
                f.write(chunk)
    return dest


def pdf_to_text(path: Path) -> str:
    text, pages = _extract(path)
    if pages == 0 or len(text) / pages >= MIN_CHARS_PER_PAGE:
        return text
    ocred = ensure_text_layer(path)
    if ocred is None:
        return text
    return _extract(ocred)[0]


def ensure_text_layer(path: Path) -> Path | None:
    """OCR `path` into a searchable sibling PDF. None if OCR is unavailable."""
    dest = path.with_suffix(".ocr.pdf")
    if dest.exists():
        return dest
    if shutil.which("ocrmypdf") is None:
        print(f"  WARN: {path.name} has no text layer and ocrmypdf is not installed "
              f"(brew install ocrmypdf) — summarizing without it.")
        return None
    proc = subprocess.run(
        ["ocrmypdf", "--skip-text", "--optimize", "0", "--quiet", str(path), str(dest)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or not dest.exists():
        print(f"  WARN: OCR failed for {path.name}: {proc.stderr.strip()[:200]}")
        return None
    return dest


def _extract(path: Path) -> Tuple[str, int]:
    with pdfplumber.open(path) as pdf:
        text = "\n\n".join((p.extract_text() or "") for p in pdf.pages).strip()
        return text, len(pdf.pages)
