#!/usr/bin/env python3
"""Check the Spanish UI strings are complete and every key a template uses exists.

Fails (exit 1) if website/_data/i18n/es.yml and en.yml carry different keys, a
template uses a `'key' | t` that en.yml lacks, or a stored translation under
website/_i18n/es/ has no `es_source_hash` (the translation note and staleness
check both key off it).

Run before building:  python3 scripts/check_i18n.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

SITE = Path(__file__).resolve().parent.parent / "website"
I18N = SITE / "_data" / "i18n"
KEY_USE = re.compile(r"'([a-z0-9_]+)'\s*\|\s*t\b")


def main() -> int:
    errors = []
    en = yaml.safe_load((I18N / "en.yml").read_text())
    es = yaml.safe_load((I18N / "es.yml").read_text())
    for k in sorted(set(en) - set(es)):
        errors.append(f"es.yml is missing '{k}'")
    for k in sorted(set(es) - set(en)):
        errors.append(f"en.yml is missing '{k}' (present in es.yml)")

    used = set()
    for sub in ("_layouts", "_includes", "es", "."):
        base = SITE / sub
        files = base.glob("*") if sub == "." else base.rglob("*")
        for p in files:
            if p.is_file() and p.suffix in {".html", ".md", ".xml"}:
                used |= set(KEY_USE.findall(p.read_text()))
    for k in sorted(used - set(en)):
        errors.append(f"a template uses '{k}', which is not in en.yml")

    for p in sorted((SITE / "_i18n" / "es").rglob("*.md")):
        if "es_source_hash" not in p.read_text().split("\n---", 1)[0]:
            errors.append(f"{p.relative_to(SITE)}: no es_source_hash")

    for e in errors:
        print(e, file=sys.stderr)
    if not errors:
        print(f"ok: {len(en)} strings, {len(used)} used")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
