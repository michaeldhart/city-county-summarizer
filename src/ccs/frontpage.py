"""Assemble the front page from the briefs written by `ccs brief`.

Selection happens in three passes, cheapest first:

  1. a date window over every brief in the archive
  2. a deterministic sort — kind, then score, then recency — which is already a
     defensible front page on its own and costs nothing
  3. one Claude call that re-orders the shortlist against each other, which is
     the part a per-meeting score genuinely cannot do: a brief scored 70 in
     isolation may or may not beat a 68 written about a different government
     three weeks earlier.

Pass 3 is optional (`--no-rerank`). Pass 2 is the fallback and the tie-break, so
the page is always reproducible even when nothing is spent.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

from . import briefs, manifest, sitegen
from .config import (
    CLAUDE_MODEL,
    DOCS_DIR,
    FRONT_PAGE_BRIEFS,
    FRONT_PAGE_VOLUME,
    FRONT_PAGE_WINDOW_DAYS,
    REPO_ROOT,
    jurisdiction_for,
    load_env,
    tracked_bodies,
)

INDEX_PATH = REPO_ROOT / "website" / "index.md"
FRONT_PAGES_DIR = REPO_ROOT / "website" / "_front_pages"
PINS_PATH = DOCS_DIR / "PINS.md"

# How far back a quiet stretch is allowed to reach before we accept a thin page.
# Six months of nothing is a broken pipeline, not a slow news month.
MAX_WINDOW_DAYS = 180
WIDEN_STEP_DAYS = 15

# The page's density gradient: one lead across the full measure, a few at a
# readable width under it, and the rest set small in more columns. Old front
# pages did this because type was expensive; it works here because rank order
# is real information and size is the cheapest way to show it.
LEAD_BRIEFS = 1
MAJOR_BRIEFS = 3


@dataclass
class Candidate:
    """A brief plus everything the page needs to print and link it."""
    brief: briefs.Brief
    date: str
    body_title: str
    government: str
    url: str

    @property
    def sort_key(self):
        # All three negated where "more is better", so one ascending sort puts
        # the strongest first: civic before summary, high score before low,
        # recent before old.
        return (
            briefs.KIND_RANK.get(self.brief.kind, 9),
            -self.brief.score,
            -date.fromisoformat(self.date).toordinal(),
        )


def next_issue() -> int:
    """One past the highest issue on disk.

    Derived by scanning rather than from a stored counter, which is what makes
    the delete-and-retry loop work: if issue 3 came out badly, delete 003.md,
    run again, and you get a new issue 3 rather than a 4 with a hole behind it.
    """
    return max(_issue_numbers(), default=0) + 1


def _issue_numbers() -> list:
    if not FRONT_PAGES_DIR.exists():
        return []
    out = []
    for f in FRONT_PAGES_DIR.glob("*.md"):
        if f.stem.isdigit():
            out.append(int(f.stem))
    return out


def issue_path(issue: int) -> Path:
    return FRONT_PAGES_DIR / f"{issue:03d}.md"


def split_front_matter(text: str) -> tuple:
    """(front_matter_dict_ish, body). Only the scalar keys we write are parsed."""
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body.lstrip("\n")


def list_issues() -> list:
    """Every issue on disk, newest first, with whichever one is currently live flagged."""
    live = None
    if INDEX_PATH.exists():
        meta, _ = split_front_matter(INDEX_PATH.read_text())
        live = meta.get("issue")
    out = []
    for n in sorted(_issue_numbers(), reverse=True):
        meta, _ = split_front_matter(issue_path(n).read_text())
        out.append({
            "issue": n,
            "generated": meta.get("generated", ""),
            "brief_count": meta.get("brief_count", "?"),
            "lead": meta.get("lead", "").strip('"'),
            "live": str(n) == str(live),
        })
    return out


def facebook_post_text(issue: int) -> tuple:
    """(headline, blurb, link) for posting a published issue to Facebook.

    Reads the numbered issue's own front matter rather than index.md, so a
    reposted back issue always says what it said when it ran, never whatever
    is currently live.
    """
    meta, _ = split_front_matter(issue_path(issue).read_text())
    headline = json.loads(meta["lead"])
    blurb = json.loads(meta["description"])
    link = f"https://belviderewire.com/issues/{issue:03d}/"
    return headline, blurb, link


def publish(issue: int) -> bool:
    """Make an existing issue the live front page again. No Claude call."""
    src = issue_path(issue)
    if not src.exists():
        return False
    meta, body = split_front_matter(src.read_text())
    INDEX_PATH.write_text(_index_front_matter(meta) + body)
    return True


def _index_front_matter(meta: dict) -> str:
    """index.md's own front matter, carrying the issue's metadata across.

    layout is set explicitly rather than left to the site defaults: an ordinary
    page defaults to `page`, which would wrap the front page in a
    data-pagefind-body and put every headline into the search index twice.
    """
    # Not title: index.md is in header_pages, so its title is the nav label and
    # has to stay "Home". description does carry across, so a share of the bare
    # domain describes the current lead rather than falling back to the site
    # blurb — the one preview field the homepage can still get right.
    keep = ("description", "issue", "generated", "window_start", "brief_count", "lead")
    lines = ["---", "layout: front-page", "title: Home"]
    lines += [f"{k}: {meta[k]}" for k in keep if k in meta]
    lines += ["---", "", "<!-- GENERATED by `ccs front-page`. Edits here are overwritten. -->", ""]
    return "\n".join(lines) + "\n"


def load_pins() -> dict:
    """{brief_id: note} from docs/PINS.md. Same runtime-parsed pattern as SCOPE.md."""
    if not PINS_PATH.exists():
        return {}
    pins = {}
    for line in PINS_PATH.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 1:
            continue
        m = re.search(r"`([^`]+#[0-9a-f]{4})`", cells[0])
        if m:
            pins[m.group(1)] = cells[1] if len(cells) > 1 else ""
    return pins


def all_candidates() -> list:
    """Every brief in the archive, resolved against its meeting record."""
    bodies = {b.id: b for b in tracked_bodies()}
    out = []
    for record in manifest.load().values():
        body = bodies.get(record.body_id)
        if body is None:
            continue
        brief_set = briefs.load(record)
        if brief_set is None:
            continue
        for b in brief_set.briefs:
            out.append(Candidate(
                brief=b,
                date=record.date,
                body_title=body.display_name,
                government=jurisdiction_for(body).display_name,
                url=sitegen.meeting_permalink(record.body_id, record.id),
            ))
    return out


def select_window(candidates: list, today: date, count: int,
                  window_days: int) -> tuple:
    """Candidates inside the window, widening it when the wire has been quiet.

    Returns (in_window, effective_days, widened). A thin page is worse than an
    honest one that reaches back a few extra weeks and says so in the folio.
    """
    days = window_days
    while True:
        start = (today - timedelta(days=days)).isoformat()
        in_window = [c for c in candidates if c.date >= start]
        if len(in_window) >= count or days >= MAX_WINDOW_DAYS:
            return in_window, days, days > window_days
        days += WIDEN_STEP_DAYS


def rank(candidates: list, count: int, rerank: bool = True) -> list:
    """Order the candidates, then take `count` — plus any pinned brief that missed the cut.

    A pin forces inclusion, never position: the brief still sits where the
    ranking put it, so pinning keeps something on the page without pretending
    it is more important than it is.
    """
    ordered = sorted(candidates, key=lambda c: c.sort_key)
    if rerank and len(ordered) > count:
        ordered = _rerank(ordered, count)

    selected = ordered[:count]
    missed_pins = [c for c in ordered[count:] if c.brief.pinned]
    if missed_pins:
        position = {id(c): i for i, c in enumerate(ordered)}
        selected = sorted(selected + missed_pins, key=lambda c: position[id(c)])
    return selected


def _rerank(ordered: list, count: int) -> list:
    """One Claude call over a shortlist, returning the full list in its order.

    Only the shortlist is sent — ranking the entire archive would cost more and
    decide nothing, since anything below the pool cannot reach the page anyway.
    Anything the model omits keeps its deterministic position at the back, so a
    truncated or malformed reply degrades to pass 2 rather than losing briefs.
    """
    pool_size = min(len(ordered), max(count * 3, count + 6))
    pool, tail = ordered[:pool_size], ordered[pool_size:]
    try:
        order = _ask_for_order(pool)
    except Exception as e:
        print(f"  re-rank failed ({e}); falling back to the deterministic order")
        return ordered

    by_id = {c.brief.id: c for c in pool}
    seen, out = set(), []
    for bid in order:
        c = by_id.get(bid)
        if c is not None and bid not in seen:
            seen.add(bid)
            out.append(c)
    out += [c for c in pool if c.brief.id not in seen]
    return out + tail


def _ask_for_order(pool: list) -> list:
    listing = "\n\n".join(
        f"id: {c.brief.id}\nkind: {c.brief.kind}\ndate: {c.date}\n"
        f"body: {c.body_title}\nheadline: {c.brief.headline}\n{c.brief.body}"
        for c in pool
    )
    prompt = f"""You are the editor of The Belvidere Wire, deciding what leads the front page.

Below are {len(pool)} briefs, each written from one public meeting of local
government in Boone County, Illinois. Put them in the order they should appear,
best first.

This publication exists to make local government visible to the people it
governs, and to give them a reason and a way to take part. Rank on how strongly
each brief serves that, judged against the others:

  - residents turned out, spoke, organized, or objected
  - a decision is still open — a vote to come, a comment period, a hearing with
    a date, a vacancy accepting applications
  - it changes what a resident pays, owns, or is allowed to do
  - it commits public money at a scale worth noticing
  - a resident would have no other way to learn it

Where two briefs cover the same story at different stages — a committee taking
something up and the full board deciding it, the same project before two
bodies — keep only the one that tells a reader the most, and rank the other
last. Each brief was written without knowing the others existed, so this is
yours to catch: a front page that runs the same story twice has wasted a slot.

Rank down: routine approvals, reports received, procedural motions, and items
whose only news is that a meeting happened. Prefer the recent when two briefs
are otherwise close, but a genuinely important item from three weeks ago beats
a dull one from yesterday. Do not rank a body up merely because it is the county
board — a school committee decision that affects families outweighs a routine
county vote.

Return ONLY a JSON array of every id above, in your chosen order. No prose.

===== BRIEFS =====
{listing}
"""
    load_env()
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    order = json.loads(text)
    return [str(x) for x in order] if isinstance(order, list) else []


def build(today: date | None = None, count: int | None = None,
          window_days: int | None = None, rerank: bool = True) -> dict:
    """Select, rank, and write website/index.md. Returns a small report for the CLI."""
    today = today or date.today()
    count = count or FRONT_PAGE_BRIEFS
    window_days = window_days or FRONT_PAGE_WINDOW_DAYS

    candidates = all_candidates()
    pins = load_pins()
    known_ids = {c.brief.id for c in candidates}
    dangling = [bid for bid in pins if bid not in known_ids]
    for c in candidates:
        if c.brief.id in pins:
            c.brief.pinned = True

    in_window, effective_days, widened = select_window(candidates, today, count, window_days)
    selected = rank(in_window, count, rerank=rerank)

    window_start = today - timedelta(days=effective_days)
    issue = next_issue()
    body = _render_body(selected, today, window_start, widened, issue)
    lead_brief = selected[0].brief if selected else None
    meta = {
        # The lead headline, not "No. N". jekyll-seo-tag takes og:title from
        # `title` verbatim and offers no other hook, so this is the headline on
        # every Facebook, Slack or iMessage preview of an issue — and "No. 1"
        # told a reader nothing. Nothing renders page.title on a front page:
        # the visible nameplate is in the body, the back-issue banner reads
        # page.issue, and /issues/ lists `lead`. Only the <title> tag moves.
        "title": json.dumps(lead_brief.headline) if lead_brief else '""',
        # Explicit, because the alternative is jekyll-seo-tag's auto-excerpt,
        # which scrapes the flag and yields "The Belvidere Wire A first draft
        # of the public record. Vol. 1 · No. 1 · ..." as the preview text.
        "description": json.dumps(lead_brief.body) if lead_brief else '""',
        "issue": str(issue),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_start": window_start.isoformat(),
        "brief_count": str(len(selected)),
        "lead": json.dumps(lead_brief.headline) if lead_brief else '""',
    }

    FRONT_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    issue_fm = "\n".join(["---"] + [f"{k}: {v}" for k, v in meta.items()] + ["---", ""])
    issue_path(issue).write_text(issue_fm + "\n" + body)
    INDEX_PATH.write_text(_index_front_matter(meta) + body)
    return {
        "issue": issue,
        "selected": len(selected),
        "in_window": len(in_window),
        "total": len(candidates),
        "window_days": effective_days,
        "widened": widened,
        "window_start": window_start,
        "pinned": sum(1 for c in selected if c.brief.pinned),
        "dangling_pins": dangling,
    }


def _render_body(selected: list, today: date, window_start: date, widened: bool,
                 issue: int) -> str:
    """The shared body of the front page and its back issue — no front matter.

    Both destinations get identical content and differ only in front matter, so
    a back issue is genuinely the edition that ran rather than a reconstruction
    of it.

    Structure carries rank: the order here is the ranking's order, and the tier
    each brief lands in (lead, major, minor) is what the stylesheet turns into
    size and column count. Reordering this output reorders the page.
    """
    issue_link = (f"<a href=\"{{{{ '/issues/' | relative_url }}}}\">No. {issue}</a>")
    folio = (f"Vol. {FRONT_PAGE_VOLUME} · {issue_link} · "
             f"{today.strftime('%A, %B %-d, %Y')}")
    quiet = (
        f"\n<p class=\"folio-note\">A quiet stretch on the wire — this edition "
        f"reaches back to {window_start.strftime('%B %-d')}.</p>\n"
        if widened else ""
    )
    parts = [
        '<div class="front-page">',
        '<header class="flag">',
        '<h1 class="nameplate">The Belvidere Wire</h1>',
        '<p class="slogan">A first draft of the public record.</p>',
        f'<p class="folio">{folio}</p>',
        "</header>",
        quiet,
    ]

    lead = selected[:LEAD_BRIEFS]
    major = selected[LEAD_BRIEFS:LEAD_BRIEFS + MAJOR_BRIEFS]
    minor = selected[LEAD_BRIEFS + MAJOR_BRIEFS:]

    for c in lead:
        parts.append(_brief_html(c, "lead"))
    if major:
        parts.append('<div class="brief-row brief-row-major">')
        parts += [_brief_html(c, "major") for c in major]
        parts.append("</div>")
    if minor:
        parts.append('<div class="brief-row brief-row-minor">')
        parts += [_brief_html(c, "minor") for c in minor]
        parts.append("</div>")

    # The disclosure has to stay true edition by edition. "No human editor chose
    # this page" is a strong claim, and it stops being true the moment a brief is
    # pinned — so the page counts its own pins rather than asserting a default.
    pinned = sum(1 for c in selected if c.brief.pinned)
    if pinned:
        human = ("%d brief%s pinned here by hand; nothing else on this page was "
                 "chosen by a person." % (pinned, "s were" if pinned > 1 else " was"))
    else:
        human = "No human editor chose this page."
    method_href = "{{ '/method/#how-the-front-page-is-chosen' | relative_url }}"

    parts += [
        '<footer class="front-page-foot">',
        '<p class="front-page-disclosure">Every brief on this page was written '
        "by a machine from the dispatch it links to, and ordered by ranking those "
        "briefs against each other. " + human + " "
        '<a href="' + method_href + '">How this page is chosen</a></p>',
        _scope_line(),
        "</footer>",
        "</div>",
        "",
    ]
    return "\n".join(parts)


# AP style, which the rest of the site's prose already follows: spell out one
# through nine, numerals from ten up.
_COUNT_WORDS = ("zero", "one", "two", "three", "four",
                "five", "six", "seven", "eight", "nine")


def _count_word(n: int) -> str:
    return _COUNT_WORDS[n] if 0 <= n < len(_COUNT_WORDS) else str(n)


def _scope_line() -> str:
    """The colophon: one sentence naming what the wire covers.

    Both counts are read from SCOPE.md rather than written down here. The front
    page is where a stranger lands first, so it is the worst place on the site
    to carry a coverage claim that quietly goes stale as bodies are added or
    dropped — /beats/ enumerates them, and this only has to agree with it.

    Deliberately nothing else: corrections and the source link live in the site
    footer, which sits directly below this on the rendered page.
    """
    bodies = tracked_bodies()
    governments = {b.jurisdiction_id for b in bodies}
    beats_href = "{{ '/beats/' | relative_url }}"
    return (
        '<p class="colophon">The Belvidere Wire follows '
        f'<a href="{beats_href}">{_count_word(len(bodies))} public bodies</a> '
        f"across {_count_word(len(governments))} Boone County governments.</p>"
    )


def _brief_html(c: Candidate, tier: str) -> str:
    """One brief as a self-contained article.

    Emitted as HTML rather than markdown because the tier has to reach the
    stylesheet, and because a brief must never be split from its link — each is
    one grid item, so a column break cannot separate them.

    Escaped on the way out: headlines carry ampersands ("Finance, Taxation &
    Salaries") often enough that this is not theoretical.
    """
    headline = html.escape(c.brief.headline, quote=False)
    body = html.escape(c.brief.body, quote=False)
    credit = html.escape(f"{c.body_title} · {_pretty(c.date)}", quote=False)
    href = "{{ '%s' | relative_url }}" % c.url
    return (
        f'<article class="brief brief-{tier}">'
        f'<h2 class="brief-headline"><a href="{href}">{headline}</a></h2>'
        f'<p class="brief-body">{body}</p>'
        f'<p class="brief-credit">{credit}</p>'
        f"</article>"
    )


def _pretty(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %-d, %Y")
