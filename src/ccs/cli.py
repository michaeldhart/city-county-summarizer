"""Command-line entry point.

Commands:
  ccs summary                           rebuild every government's About page
  ccs summary belvidere                 rebuild just one
  ccs check                             show which tracked bodies have records in a window (no Claude calls)
  ccs sync                              discover + ingest new meetings into the manifest (default: last 35 days)
  ccs sync --since YYYY-MM-DD
  ccs sync --only d100 --since ...      limit to one jurisdiction, source, or body
  ccs ingest <source>:<key>             re-ingest a specific meeting, updating the manifest
                                        diligent:<numeric id>, bccd:YYYYMMDD, swcd:YYYYMMDD
  ccs backfill-resources                fill in the Resources list on older records (no Claude calls)
  ccs brief                             write front-page briefs for meetings in a window (default: last 35 days)
  ccs brief --since YYYY-MM-DD --only bccd
  ccs front-page                        rank briefs in a window and write the front page
  ccs front-page --no-rerank            skip the ranking Claude call (deterministic, free)
  ccs front-page --list-briefs          print every brief id in the window (for docs/PINS.md)
  ccs front-page --list                 list back issues, newest first
  ccs front-page --publish 2            make an existing issue the live front page again
  ccs build-site                        regenerate website/_bodies and website/_meetings from the manifest
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from . import (briefs, config, diligent, frontpage, general, manifest, report, sitegen,
               sources, summarize)
from .config import body_for_type_id, load_env, tracked_bodies


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(prog="ccs", description="Boone County meeting monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_summary = sub.add_parser("summary", help="Rebuild About pages")
    p_summary.add_argument("jurisdiction", nargs="?", default=None,
                           help="Limit to one government (default: all)")

    p_check = sub.add_parser("check", help="Preview which bodies have records in a window (no Claude calls)")
    p_check.add_argument("--since", type=_parse_date, default=None,
                         help="Window start (default: 35 days ago)")
    p_check.add_argument("--only", default=None,
                         help="Comma-separated body ids, sources, or jurisdictions")

    p_sync = sub.add_parser("sync", help="Discover and ingest new meetings into the manifest")
    p_sync.add_argument("--since", type=_parse_date, default=None,
                        help="Window start (default: 35 days ago)")
    p_sync.add_argument("--only", default=None,
                        help="Comma-separated body ids, sources, or jurisdictions")

    p_ingest = sub.add_parser("ingest", help="Force-ingest a specific meeting")
    p_ingest.add_argument("meeting_id", help="e.g. diligent:1622, bccd:20260420, swcd:20260701")

    p_backfill = sub.add_parser(
        "backfill-resources",
        help="Fill in the Resources list on records ingested before it existed (no Claude calls)")
    p_backfill.add_argument("--only", default=None,
                            help="Comma-separated body ids, sources, or jurisdictions")

    p_brief = sub.add_parser(
        "brief", help="Write front-page briefs for meetings in a window")
    p_brief.add_argument("--since", type=_parse_date, default=None,
                         help="Window start (default: 35 days ago)")
    p_brief.add_argument("--only", default=None,
                         help="Comma-separated body ids, sources, or jurisdictions")
    p_brief.add_argument("--force", action="store_true",
                         help="Re-write briefs even where the summary is unchanged")

    p_front = sub.add_parser(
        "front-page", help="Rank recent briefs and write the front page")
    p_front.add_argument("--count", type=int, default=None,
                         help=f"Briefs on the page (default: {config.FRONT_PAGE_BRIEFS})")
    p_front.add_argument("--window-days", type=int, default=None,
                         help=f"How far back to look (default: {config.FRONT_PAGE_WINDOW_DAYS})")
    p_front.add_argument("--no-rerank", action="store_true",
                         help="Skip the ranking Claude call; use the deterministic order")
    p_front.add_argument("--list-briefs", action="store_true",
                         help="Print every brief id in the window and exit, for pinning")
    p_front.add_argument("--list", action="store_true", dest="list_issues",
                         help="List back issues and exit")
    p_front.add_argument("--publish", type=int, default=None, metavar="N",
                         help="Re-publish an existing issue as the front page (no Claude call)")

    sub.add_parser("build-site", help="Regenerate the Jekyll site's content from the manifest")

    args = parser.parse_args(argv)
    if args.command == "summary":
        return _cmd_summary(args.jurisdiction)
    if args.command == "check":
        return _cmd_check(args.since, _parse_only(args.only))
    if args.command == "sync":
        return _cmd_sync(args.since, _parse_only(args.only))
    if args.command == "ingest":
        return _cmd_ingest(args.meeting_id)
    if args.command == "backfill-resources":
        return _cmd_backfill_resources(_parse_only(args.only))
    if args.command == "brief":
        return _cmd_brief(args.since, _parse_only(args.only), args.force)
    if args.command == "front-page":
        return _cmd_front_page(args.count, args.window_days,
                               not args.no_rerank, args.list_briefs,
                               args.list_issues, args.publish)
    if args.command == "build-site":
        return _cmd_build_site()
    parser.error(f"unknown command {args.command}")
    return 2


def _cmd_summary(jurisdiction: str | None) -> int:
    if jurisdiction is not None and jurisdiction not in general.SPECS_BY_ID:
        print(f"error: no About page for '{jurisdiction}'. "
              f"Known: {', '.join(sorted(general.SPECS_BY_ID))}", file=sys.stderr)
        return 2
    index = general.write_about_index()
    paths = ([general.build_about_page(jurisdiction)] if jurisdiction
             else general.build_all())
    print()
    for path in [index] + paths:
        print(f"Wrote {path.relative_to(config.REPO_ROOT)} ({path.stat().st_size} bytes)")
    return 0


def _cmd_check(since: date | None, only: set | None) -> int:
    today = date.today()
    since = since or (today - timedelta(days=35))
    if _no_match(only):
        return 2
    print(f"Checking sources for {since} → {today}...\n")
    rows = report.check_sources(since, today, only=only)
    _print_check_table(rows)
    have = sum(1 for _, ok in rows if ok)
    print(f"\n{have} of {len(rows)} tracked bodies have records in this window.")
    return 0


def _print_check_table(rows: list[tuple[str, bool]]) -> None:
    header = ("Source", "Records")
    name_w = max(len(header[0]), max((len(name) for name, _ in rows), default=0))
    status_w = max(len(header[1]), 3)
    border = "+" + "-" * (name_w + 2) + "+" + "-" * (status_w + 2) + "+"
    print(border)
    print(f"| {header[0]:<{name_w}} | {header[1]:<{status_w}} |")
    print(border)
    for name, has in rows:
        icon = "✅" if has else "❌"
        print(f"| {name:<{name_w}} | {icon:<{status_w}} |")
    print(border)


def _cmd_sync(since: date | None, only: set | None) -> int:
    today = date.today()
    since = since or (today - timedelta(days=35))
    if since > today:
        print(f"error: --since {since} is in the future", file=sys.stderr)
        return 2
    if _no_match(only):
        return 2

    print(f"Syncing: {since} → {today}")
    print(f"Tracked bodies: {[b.id for b in report.select_bodies(only)]}")

    entries = report.sync_meetings(since=since, today=today, only=only)
    print(f"\n{len(entries)} meeting(s) in window. Run `ccs build-site` to refresh the site.")
    return 0


def _cmd_ingest(meeting_id: str) -> int:
    if ":" not in meeting_id:
        print("error: meeting_id must be like source:key (e.g. diligent:1622)", file=sys.stderr)
        return 2
    source, key = meeting_id.split(":", 1)

    src = sources.SOURCES.get(source)
    if isinstance(src, sources.DiligentSource):
        return _ingest_diligent(source, src.base, key)
    if isinstance(src, sources.PdfIndexSource):
        return _ingest_pdf_meeting(source, key, src.list_meetings)
    known = ", ".join(sorted(sources.SOURCES))
    print(f"error: unknown source '{source}' (expected one of: {known})", file=sys.stderr)
    return 2


def _ingest_diligent(source: str, base: str, key: str) -> int:
    if not key.isdigit():
        print(f"error: {source} key must be a numeric meeting id, got '{key}'", file=sys.stderr)
        return 2
    target_id = int(key)
    ref = next((m for m in diligent.list_meetings(base) if m.id == target_id), None)
    if ref is None:
        print(f"error: no {source} meeting with id={target_id}", file=sys.stderr)
        return 1
    body = body_for_type_id(source, ref.type_id)
    if body is None:
        print(f"error: {source} type_id {ref.type_id} ('{ref.type_name}') isn't in the body registry",
              file=sys.stderr)
        return 1
    print(f"Ingesting {ref.date} {ref.title} (body={body.id})")
    videos = report.list_videos_by_jurisdiction([body]).get(body.jurisdiction_id)
    record = summarize.ingest_diligent(base, source, ref, body, videos=videos)
    manifest.upsert(record)
    print(f"OK  transcript={record.has_transcript}  summary={record.summary_path}")
    return 0


def _ingest_pdf_meeting(source: str, key: str, lister) -> int:
    meetings = lister()
    meeting = next((m for m in meetings if m.key == key), None)
    if meeting is None:
        recent = ", ".join(m.key for m in meetings[:5])
        print(f"error: no {source} meeting with key '{key}'. Most recent: {recent}",
              file=sys.stderr)
        return 1
    # A multi-body source serves several bodies, so the meeting picks the body —
    # not the first tracked body that happens to share the source.
    tracked = {b.id: b for b in tracked_bodies()}
    if meeting.body_id is not None:
        body = tracked.get(meeting.body_id)
    else:
        body = next((b for b in tracked.values() if b.source == source), None)
    if body is None:
        print(f"error: no tracked body for '{source}' meeting '{key}' (check SCOPE.md)",
              file=sys.stderr)
        return 1
    print(f"Ingesting {source} meeting on {meeting.date} ({meeting.name or body.display_name})")
    videos = report.list_videos_by_jurisdiction([body]).get(body.jurisdiction_id)
    record = summarize.ingest_pdf_meeting(source, meeting, body, videos=videos)
    manifest.upsert(record)
    print(f"OK  transcript={record.has_transcript}  summary={record.summary_path}")
    return 0


def _cmd_backfill_resources(only: set | None) -> int:
    if _no_match(only):
        return 2
    filled, partial = report.backfill_resources(only)
    if not filled:
        print("No records needed backfilling.")
        return 0
    print(f"Filled resources on {filled} record(s).")
    if partial:
        print(f"{partial} were only partly reconstructed — the source index or the "
              f"cached agenda no longer covers them.")
    print("Run `ccs build-site` to refresh the site.")
    return 0


def _cmd_brief(since: date | None, only: set | None, force: bool) -> int:
    since = since or (date.today() - timedelta(days=35))
    if _no_match(only):
        return 2
    wanted = {b.id for b in report.select_bodies(only)}
    records = [r for r in manifest.load().values()
               if r.body_id in wanted and r.date >= since.isoformat()]
    records.sort(key=lambda r: r.date)
    if not records:
        print(f"No ingested meetings on or after {since}. Nothing to brief.")
        return 0

    print(f"Briefing {len(records)} meeting(s) from {since} onward\n")
    written = skipped = failed = total = 0
    for record in records:
        summary = briefs.summary_text_for(record)
        label = f"{record.date}  {record.body_id}"
        if summary is None:
            print(f"  {label}  — no summary on disk, skipped")
            skipped += 1
            continue
        if not force and briefs.is_current(record, summary):
            print(f"  {label}  — unchanged, skipped")
            skipped += 1
            continue
        items = briefs.generate(record)
        if not items:
            print(f"  {label}  — FAILED (no usable briefs returned)")
            failed += 1
            continue
        briefs.write(record, items, briefs.fingerprint(summary))
        kinds = ", ".join(b.kind for b in items)
        print(f"  {label}  — {len(items)} brief(s) [{kinds}]")
        written += 1
        total += len(items)

    print(f"\n{total} brief(s) across {written} meeting(s). "
          f"{skipped} skipped, {failed} failed.")
    return 1 if failed and not written else 0


def _cmd_front_page(count: int | None, window_days: int | None,
                    rerank: bool, list_briefs: bool,
                    list_issues: bool = False, publish: int | None = None) -> int:
    count = count or config.FRONT_PAGE_BRIEFS
    window_days = window_days or config.FRONT_PAGE_WINDOW_DAYS

    if list_issues:
        issues = frontpage.list_issues()
        if not issues:
            print("No issues yet. Run `ccs front-page` to publish the first.")
            return 0
        for i in issues:
            live = "  ← live" if i["live"] else ""
            print(f"No. {i['issue']:<4} {i['generated'][:10]}  "
                  f"{i['brief_count']:>2} briefs  {i['lead']}{live}")
        print(f"\n{len(issues)} issue(s). Next run publishes No. {frontpage.next_issue()}.")
        return 0

    if publish is not None:
        if not frontpage.publish(publish):
            print(f"error: no issue No. {publish}. `ccs front-page --list` shows what exists.",
                  file=sys.stderr)
            return 1
        print(f"Published No. {publish} as the front page.")
        return 0

    if list_briefs:
        cands = frontpage.all_candidates()
        in_window, days, _ = frontpage.select_window(cands, date.today(), count, window_days)
        for c in sorted(in_window, key=lambda c: c.sort_key):
            print(f"`{c.brief.id}`  [{c.brief.kind} {c.brief.score}]  {c.brief.headline}")
        print(f"\n{len(in_window)} brief(s) in the last {days} days.")
        return 0

    if not frontpage.all_candidates():
        print("No briefs found. Run `ccs brief` first.", file=sys.stderr)
        return 1

    report_ = frontpage.build(count=count, window_days=window_days, rerank=rerank)
    for bid in report_["dangling_pins"]:
        print(f"warning: pinned brief `{bid}` no longer exists — it was probably "
              f"re-written under a new headline. Update docs/PINS.md.", file=sys.stderr)
    if report_["widened"]:
        print(f"Quiet stretch: widened the window to {report_['window_days']} days "
              f"(back to {report_['window_start']}) to fill the page.")
    print(f"Published No. {report_['issue']} — "
          f"{report_['selected']} brief(s) from {report_['in_window']} in window "
          f"({report_['total']} in the archive)"
          + (f", {report_['pinned']} pinned" if report_["pinned"] else ""))
    print(f"  {frontpage.issue_path(report_['issue']).relative_to(config.REPO_ROOT)}"
          f" → {frontpage.INDEX_PATH.relative_to(config.REPO_ROOT)}")
    return 0


def _cmd_build_site() -> int:
    n_bodies, n_meetings = sitegen.build_site_content()
    print(f"Wrote {n_bodies} body page(s) and {n_meetings} meeting page(s) "
          f"to {sitegen.WEBSITE_DIR.relative_to(config.REPO_ROOT)}/")
    return 0


def _parse_only(value: str | None) -> set | None:
    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def _no_match(only: set | None) -> bool:
    """True (after printing) when a --only filter selects nothing — a silent
    no-op here looks identical to 'nothing new to ingest'."""
    if only and not report.select_bodies(only):
        print(f"error: --only {sorted(only)} matched no tracked body. "
              f"Known: {sorted({b.id for b in tracked_bodies()} | {b.source for b in tracked_bodies()})}",
              file=sys.stderr)
        return True
    return False


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got '{s}'")


if __name__ == "__main__":
    sys.exit(main())
