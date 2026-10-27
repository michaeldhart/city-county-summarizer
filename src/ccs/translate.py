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


class Rejected(Exception):
    """A reply that parsed badly or failed validation; worth one more try."""


def build_prompt(src) -> str:
    return _build_page_prompt(src) if isinstance(src, PageSource) else _build_prompt(src)


def _finish(src, raw: str) -> Path:
    """Parse, validate and write one reply, or raise Rejected with why."""
    try:
        if isinstance(src, PageSource):
            parsed = _parse_page(raw, src)
            problem = check_page(src.body, parsed["body"])
            for k, v in src.fields:
                problem = problem or check_plain(v, parsed[k])
            writer = _write_page
        else:
            parsed = _parse(raw)
            problem = check(src.body, parsed["body"]) or check_plain(src.description, parsed["description"])
            writer = _write
    except TranslationError as e:
        raise Rejected(str(e))
    if problem:
        raise Rejected(problem)
    return writer(src, parsed)


def translate_item(src, first_raw: str | None = None) -> Path:
    """One Claude call (two if validation catches a dropped figure). Writes the store file.

    `first_raw` is a reply already in hand (from a batch), used in place of the
    first call; a rejection then costs one ordinary call, same as it would have.
    """
    prompt = build_prompt(src)
    problem = None
    raw = first_raw
    for _ in range(2):
        if raw is None:
            raw = _call_claude(prompt if problem is None else
                               prompt + f"\n\nYour previous attempt was rejected: {problem}\n"
                                        "Translate again, fixing exactly that.\n")
        try:
            return _finish(src, raw)
        except Rejected as e:
            problem, raw = str(e), None
    raise TranslationError(f"{src.name}: {problem}")


BATCH_FILE = REPO_ROOT / "data" / "translate_batch.json"
_POLL_SECS = 30


def _custom_id(src) -> str:
    key = f"p_{src.store}" if isinstance(src, PageSource) else f"m_{src.name}"
    return re.sub(r"[^A-Za-z0-9_-]", "_", key)[:64]


def run_batch(srcs: list, batch_id: str | None = None, log=print) -> tuple:
    """Translate through the Batch API (half price, results within the hour or so).

    Submits one request per source, polls until the batch ends, then writes each
    reply through the same validation as translate_item. Returns (done, failed
    names). The batch id is saved to data/translate_batch.json the moment it is
    created, so a run interrupted while waiting can be collected with
    `--batch-id`; replies already written are skipped by the normal is-current
    check next time.
    """
    import json
    import time

    load_env()
    client = anthropic.Anthropic()
    by_id = {_custom_id(s): s for s in srcs}
    if len(by_id) != len(srcs):
        raise TranslationError("batch custom ids collide")

    if batch_id is None:
        batch = client.messages.batches.create(requests=[
            {"custom_id": cid, "params": {
                "model": CLAUDE_MODEL, "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": build_prompt(s)}]}}
            for cid, s in by_id.items()])
        batch_id = batch.id
        BATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
        BATCH_FILE.write_text(json.dumps({"id": batch_id, "count": len(by_id)}))
        log(f"Submitted batch {batch_id} ({len(by_id)} requests)")
    else:
        log(f"Collecting batch {batch_id}")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        c = batch.request_counts
        log(f"  waiting: {c.succeeded} succeeded, {c.errored} errored, {c.processing} processing")
        time.sleep(_POLL_SECS)

    done, failed = 0, []
    for entry in client.messages.batches.results(batch_id):
        src = by_id.get(entry.custom_id)
        if src is None:
            continue
        raw = None
        if entry.result.type == "succeeded" and entry.result.message.stop_reason != "max_tokens":
            raw = entry.result.message.content[0].text
        try:
            translate_item(src, first_raw=raw)
        except TranslationError as e:
            log(f"  {src.name}  — FAILED: {e}")
            failed.append(src.name)
            continue
        done += 1
        log(f"  {src.name}  — done" + ("" if raw else " (retried outside the batch)"))
    return done, failed


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


# A figure is compared by value, not spelling: "$600K" and "$600,000" are the
# same figure, and so are "FY27" and "2027".
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)([KkMm]\b| (?:million|millones|millón|thousand|mil)\b)?")
_ORD_EN = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b")
# "1st Tuesday" is "primer martes": the figure becomes a word, which is correct.
_ORD_ES = re.compile(r"\b\d+(?:\.?[ºª°]|\.er)(?!\w)")

_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
_ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
                  "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
                  "twelfth": 12, "twentieth": 20, "thirtieth": 30}


def _norm(num: str, suffix: str | None) -> str:
    v = num.replace(",", "")
    if suffix:
        from decimal import Decimal
        v = str(int(Decimal(v) * (1000 if suffix in ("K", "k", " thousand", " mil") else 1_000_000)))
    if re.fullmatch(r"20[2-3]\d", v):
        v = v[2:]
    return v


def _nums(text: str) -> Counter:
    return Counter(_norm(n, k) for n, k in _NUM.findall(_ORD_ES.sub(" ", _ORD_EN.sub(" ", text))))


def _written(english: str) -> set:
    """Values the English spells out in words, which Spanish may legitimately write as digits."""
    out = set()
    low = english.lower()
    for w in re.findall(r"[a-z]+(?:-[a-z]+)?", low):
        parts = w.split("-")
        if len(parts) == 2 and parts[0] in _TENS and (parts[1] in _UNITS or parts[1] in _ORDINAL_WORDS):
            out.add(str(_TENS[parts[0]] + (_UNITS.get(parts[1]) or _ORDINAL_WORDS[parts[1]])))
        for part in parts:
            for table in (_UNITS, _TENS, _ORDINAL_WORDS):
                if part in table:
                    out.add(str(table[part]))
        if w in ("hundred", "dozen"):
            out.add("100" if w == "hundred" else "12")
    if re.search(r"\b(noon|midnight)\b", low):
        out |= {"12", "0", "00"}
    return out


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
    optional = Counter(_norm(n, None) for n in _ORD_EN.findall(english))
    allowed = _written(english)
    missing = _nums(english) - _nums(spanish)
    extra = Counter({k: v for k, v in ((_nums(spanish) - _nums(english)) - optional).items()
                     if k not in allowed})
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
