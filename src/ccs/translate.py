"""Spanish translations of the site's English content, kept in a committed store.

The store is `website/_i18n/es/`, read by the Jekyll plugin (`_plugins/i18n.rb`)
to build the `/es/` pages. It is committed because `data/` is not: the weekly
run happens on another machine, and `build-site` wipes and rewrites the English
collections, so a translation has to live somewhere it survives both.

The source is the English page already under `website/`, not `data/`, so a
translation can be made from any checkout. Each stored file records a hash of
the English it came from; `ccs translate` re-translates only what is missing or
whose English has since changed, so a bare re-run costs nothing where nothing
moved — the same shape as `ccs brief`.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import yaml

from .config import CLAUDE_MODEL, DOCS_DIR, REPO_ROOT, load_env

WEBSITE_DIR = REPO_ROOT / "website"
MEETINGS_DIR = WEBSITE_DIR / "_meetings"
STORE_DIR = WEBSITE_DIR / "_i18n" / "es"
GLOSSARY_PATH = DOCS_DIR / "GLOSSARY_ES.md"

MAX_TOKENS = 8000
PLACEHOLDERS = ("_Nothing filed", "_Summary file missing")

# Rough Sonnet rates, $/Mtok, for `--dry-run`'s estimate only.
_PRICE_IN, _PRICE_OUT = 3.0, 15.0
_CHARS_PER_TOKEN = 3.5
_OUT_PER_IN = 1.3


class TranslationError(Exception):
    pass


@dataclass
class Source:
    name: str            # file stem: "diligent-1622"
    body_id: str
    date: str
    title: str
    description: str
    body: str

    @property
    def fingerprint(self) -> str:
        blob = "\n\x1f".join([self.title, self.description, self.body])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def split_front_matter(text: str) -> tuple:
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.S)
    if not m:
        raise ValueError("no front matter")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def store_path(name: str) -> Path:
    return STORE_DIR / "meetings" / f"{name}.md"


def load_sources() -> list:
    out = []
    for p in sorted(MEETINGS_DIR.glob("*.md")):
        meta, body = split_front_matter(p.read_text())
        body = body.strip()
        if not body or body.startswith(PLACEHOLDERS):
            continue
        out.append(Source(
            name=p.stem,
            body_id=meta.get("body_id", ""),
            date=str(meta.get("date", "")),
            title=meta.get("title", ""),
            description=meta.get("description", "") or "",
            body=body,
        ))
    return out


def stored_hash(name: str) -> str | None:
    p = store_path(name)
    if not p.exists():
        return None
    meta, _ = split_front_matter(p.read_text())
    return meta.get("es_source_hash")


def is_current(src: Source) -> bool:
    return stored_hash(src.name) == src.fingerprint


def estimate_cost(src: Source) -> float:
    toks_in = len(src.body + src.description + src.title) / _CHARS_PER_TOKEN + 1500
    return (toks_in * _PRICE_IN + toks_in * _OUT_PER_IN * _PRICE_OUT) / 1e6


@dataclass
class PageSource:
    """An English page translated as one piece: a static page or a front-page issue."""
    name: str            # label: "about/bpd.md", "issue 004"
    store: str           # path under the store: "pages/about/bpd.md", "front_pages/004.md"
    title: str
    body: str            # Liquid comments already stripped
    fields: tuple = ()   # more front matter to translate beside the title: (("description", "..."), ...)

    @property
    def fingerprint(self) -> str:
        blob = "\n\x1f".join([self.title, *(v for _, v in self.fields), self.body])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


PAGE_NAMES = ("method.md", "why.md", "about.md")
_LIQUID_COMMENT = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}\s*", re.S)


FRONT_PAGES_DIR = WEBSITE_DIR / "_front_pages"
INDEX_PATH = WEBSITE_DIR / "index.md"
ISSUE_FIELDS = ("description", "lead")


def load_page_sources() -> list:
    paths = [WEBSITE_DIR / n for n in PAGE_NAMES] + sorted((WEBSITE_DIR / "about").glob("*.md"))
    out = []
    for p in paths:
        meta, body = split_front_matter(p.read_text())
        body = _LIQUID_COMMENT.sub("", body).strip()
        name = str(p.relative_to(WEBSITE_DIR))
        out.append(PageSource(name=name, store=f"pages/{name}", title=meta.get("title", ""), body=body))
    return out


def load_issue_sources() -> list:
    out = []
    for p in sorted(FRONT_PAGES_DIR.glob("*.md")):
        meta, body = split_front_matter(p.read_text())
        out.append(PageSource(
            name=f"issue {p.stem}", store=f"front_pages/{p.name}", title=meta.get("title", ""),
            body=body.strip(),
            fields=tuple((k, meta[k]) for k in ISSUE_FIELDS if meta.get(k))))
    return out


def is_page_current(src: PageSource) -> bool:
    p = STORE_DIR / src.store
    if not p.exists():
        return False
    meta, _ = split_front_matter(p.read_text())
    return meta.get("es_source_hash") == src.fingerprint


def estimate_page_cost(src: PageSource) -> float:
    toks_in = len(src.body + src.title + "".join(v for _, v in src.fields)) / _CHARS_PER_TOKEN + 1500
    return (toks_in * _PRICE_IN + toks_in * _OUT_PER_IN * _PRICE_OUT) / 1e6


def translate_page(src: PageSource) -> Path:
    """Like translate_meeting, for a static page. Writes the store file."""
    prompt = _build_page_prompt(src)
    problem = None
    for _ in range(2):
        raw = _call_claude(prompt if problem is None else
                           prompt + f"\n\nYour previous attempt was rejected: {problem}\n"
                                    "Translate again, fixing exactly that.\n")
        parsed = _parse_page(raw, src)
        problem = check_page(src.body, parsed["body"])
        for k, v in src.fields:
            problem = problem or check_plain(v, parsed[k])
        if problem is None:
            return _write_page(src, parsed)
    raise TranslationError(f"{src.name}: {problem}")


def _build_page_prompt(src: PageSource) -> str:
    glossary = GLOSSARY_PATH.read_text()
    sections = [("TITLE", src.title)] + [(k.upper(), v) for k, v in src.fields] + [("BODY", src.body)]
    hints = {"TITLE": "the page title", "BODY": "the page, in Markdown or HTML"}
    reply = "\n".join(f"==={k}===\n({hints.get(k, k.lower())})" for k, _ in sections)
    source = "\n".join(f"==={k}===\n{v}" for k, v in sections)
    return f"""You are translating a page of The Belvidere Wire into Spanish. The Wire
publishes machine-written accounts of the public meetings of local government in
Boone County, Illinois. Your Spanish edition sits beside the English one; the
English governs.

Translate faithfully and completely. Do not add, omit, soften or sharpen
anything. Every number, date, dollar amount, address, phone number and name must
survive. Where the page speaks in the first person (the publisher's own voice),
keep the first person.

Keep the Markdown and HTML exactly as they are: the same headings, in the same
order, the same bullets, tables, bold and line breaks. Leave every URL, every
Liquid tag ({{{{ ... }}}} and {{% ... %}}) and every kramdown attribute line
(`{{: ... }}`) character for character; translate only the words around them and
the visible text of links. Keep HTML tags and their attributes unchanged, and
translate only the text between them.

Follow this glossary and style guide. It decides what stays in English, what is
translated, and how.

{glossary}

Reply in exactly this format, with these marker lines and nothing else
before, between or after the sections:

{reply}

{source}
"""


def _parse_page(raw: str, src: PageSource) -> dict:
    want = {"TITLE", "BODY", *(k.upper() for k, _ in src.fields)}
    parts = re.split(r"^===([A-Z]+)===[ \t]*$", raw, flags=re.M)
    found = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if set(found) != want or not found["BODY"]:
        raise TranslationError(f"reply did not have the sections {sorted(want)}: {sorted(found)}")
    return {k.lower(): v for k, v in found.items()}


_LIQUID = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
_IAL = re.compile(r"^\{:.*\}\s*$", re.M)
_URL = re.compile(r"\]\(([^)\s]+)|href=\"([^\"]+)\"")


def check_page(english: str, spanish: str) -> str | None:
    """check(), plus what only a page carries: Liquid, kramdown attributes, link targets."""
    for pat, what in ((_LIQUID, "Liquid tags"), (_IAL, "kramdown attributes"), (_URL, "link targets")):
        a, b = Counter(pat.findall(english)), Counter(pat.findall(spanish))
        if a != b:
            return f"{what} differ — missing: {sorted((a - b).elements())[:4]}, added: {sorted((b - a).elements())[:4]}"
    return check(english, spanish)


def _write_page(src: PageSource, parsed: dict) -> Path:
    p = STORE_DIR / src.store
    p.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": parsed["title"],
        **{k: parsed[k] for k, _ in src.fields},
        "es_source_hash": src.fingerprint,
        "es_model": CLAUDE_MODEL,
        "es_translated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10_000)
    # The reader is on /es/, so a link into the site should land on the Spanish
    # twin where there is one; the `loc` filter falls back to the English URL.
    body = parsed["body"].replace("| relative_url", "| loc | relative_url")
    p.write_text(f"---\n{fm}---\n\n{body}\n")
    return p


def sync_index() -> str:
    """Keep the Spanish home page in step with the live issue. Free: no Claude call.

    index.md is a copy of one issue's body under different front matter (see
    frontpage.publish), so the Spanish home page is that issue's stored
    translation under the same swap. Returns a one-line status.
    """
    if not INDEX_PATH.exists():
        return "no index.md"
    meta, body = split_front_matter(INDEX_PATH.read_text())
    body = re.sub(r"<!--.*?-->\s*", "", body, flags=re.S).strip()
    issue = meta.get("issue")
    fp = hashlib.sha256(f"{issue}\x1f{body}".encode("utf-8")).hexdigest()[:16]
    dest = STORE_DIR / "index.md"
    if dest.exists() and split_front_matter(dest.read_text())[0].get("es_source_hash") == fp:
        return "Spanish home page current"
    src = STORE_DIR / "front_pages" / f"{int(issue):03d}.md"
    if not src.exists():
        return f"Spanish home page not updated: issue {issue} has no translation yet"
    es_meta, es_body = split_front_matter(src.read_text())
    out = {k: v for k, v in meta.items() if k in ("issue", "generated", "window_start", "brief_count")}
    out.update({"title": "Inicio", "description": es_meta.get("description", ""),
                "lead": es_meta.get("lead", ""), "es_source_hash": fp,
                "es_model": es_meta.get("es_model"), "es_translated_at": es_meta.get("es_translated_at")})
    fm = yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=10_000)
    dest.write_text(f"---\n{fm}---\n\n{es_body.strip()}\n")
    return f"Spanish home page set to issue {issue}"


def translate_meeting(src: Source) -> Path:
    """One Claude call (two if validation catches a dropped figure). Writes the store file."""
    prompt = _build_prompt(src)
    problem = None
    for _ in range(2):
        raw = _call_claude(prompt if problem is None else
                           prompt + f"\n\nYour previous attempt was rejected: {problem}\n"
                                    "Translate again, fixing exactly that.\n")
        parsed = _parse(raw)
        problem = check(src.body, parsed["body"]) or check_plain(src.description, parsed["description"])
        if problem is None:
            return _write(src, parsed)
    raise TranslationError(f"{src.name}: {problem}")


def _build_prompt(src: Source) -> str:
    glossary = GLOSSARY_PATH.read_text()
    return f"""You are translating a dispatch from The Belvidere Wire into Spanish. The Wire
publishes a machine-written account of every public meeting of local government
in Boone County, Illinois. Its readers include Spanish speakers in Belvidere.
Your Spanish edition sits beside the English one; the English governs.

Translate faithfully and completely. Do not add, omit, soften or sharpen
anything: if the English reports a vote count, a dollar figure or a name, the
Spanish reports the same one. Do not characterize, and do not explain.

Keep the Markdown exactly as it is: the same headings, in the same order, the
same bullets, bold and line breaks. Every number, dollar amount, percentage and
vote count must survive unchanged.

Follow this glossary and style guide. It decides what stays in English, what is
translated, and how.

{glossary}

Reply in exactly this format, with these three marker lines and nothing else
before, between or after the sections:

===TITLE===
(the meeting title)
===DESCRIPTION===
(the description, one paragraph)
===BODY===
(the dispatch, in Markdown)

===TITLE===
{src.title}
===DESCRIPTION===
{src.description}
===BODY===
{src.body}
"""


_SECTION = re.compile(r"^===(TITLE|DESCRIPTION|BODY)===[ \t]*$", re.M)


def _parse(raw: str) -> dict:
    parts = _SECTION.split(raw)
    # split with one capture group: [pre, name, text, name, text, ...]
    found = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if set(found) != {"TITLE", "DESCRIPTION", "BODY"} or not found["BODY"]:
        raise TranslationError(f"reply did not have all three sections: {sorted(found)}")
    return {k.lower(): v for k, v in found.items()}


_NUM = re.compile(r"\d+(?:[.,]\d+)*")


# "1st Tuesday" is "primer martes": the figure becomes a word, which is correct.
_ORDINAL = re.compile(r"\b\d+(?:st|nd|rd|th)\b|\b\d+(?:\.?[ºª°]|\.er)(?!\w)")


def _nums(text: str) -> Counter:
    return Counter(_NUM.findall(_ORDINAL.sub(" ", text)))


def check(english: str, spanish: str) -> str | None:
    """A reason the translation can't be trusted, or None.

    Cheap structural checks: a model that drops a bullet or a figure is the
    failure that matters, and one that merely phrases something awkwardly is
    what the unreviewed label is for.
    """
    def count(prefix, text):
        return sum(1 for ln in text.splitlines() if ln.lstrip().startswith(prefix))

    for prefix, what in (("#", "headings"), ("- ", "bullets")):
        a, b = count(prefix, english), count(prefix, spanish)
        if a != b:
            return f"{what}: English has {a}, Spanish has {b}"
    return check_plain(english, spanish)


def check_plain(english: str, spanish: str) -> str | None:
    missing = _nums(english) - _nums(spanish)
    extra = _nums(spanish) - _nums(english)
    if missing or extra:
        return (f"figures differ — missing from Spanish: {sorted(missing.elements())[:8]}, "
                f"added in Spanish: {sorted(extra.elements())[:8]}")
    return None


def _write(src: Source, parsed: dict) -> Path:
    p = store_path(src.name)
    p.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": parsed["title"],
        "description": parsed["description"],
        "es_source_hash": src.fingerprint,
        "es_model": CLAUDE_MODEL,
        "es_translated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if not src.description:
        del meta["description"]
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10_000)
    p.write_text(f"---\n{fm}---\n\n{parsed['body']}\n")
    return p


def _call_claude(prompt: str) -> str:
    load_env()
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "max_tokens":
        raise TranslationError("reply hit the token limit")
    return resp.content[0].text
