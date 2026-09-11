"""Command-line entry point.

Commands:
  ccs summary                           rebuild general_summary.md
  ccs check                             show which tracked bodies have records in a window (no Claude calls)
  ccs report                            recap report (default: last 35 days)
  ccs report --since YYYY-MM-DD
  ccs ingest diligent:<id>              re-ingest a specific meeting, updating the manifest
  ccs ingest bccd:YYYYMMDD
  ccs ingest swcd:YYYYMMDD
  ccs build-site                        regenerate website/_bodies and website/_meetings from the manifest
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from . import bccd, config, diligent, general, manifest, report, sitegen, summarize, swcd, youtube
from .config import body_for_type_id, load_env, tracked_bodies


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(prog="ccs", description="Boone County meeting monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", help="Rebuild the general_summary.md living doc")

    p_check = sub.add_parser("check", help="Preview which bodies have records in a window (no Claude calls)")
    p_check.add_argument("--since", type=_parse_date, default=None,
                         help="Window start (default: 35 days ago)")

    p_report = sub.add_parser("report", help="Generate a recap report")
    p_report.add_argument("--since", type=_parse_date, default=None,
                          help="Recap window start (default: 35 days ago)")

    p_ingest = sub.add_parser("ingest", help="Force-ingest a specific meeting")
    p_ingest.add_argument("meeting_id", help="e.g. diligent:1622, bccd:20260420, swcd:20260701")

    sub.add_parser("build-site", help="Regenerate the Jekyll site's content from the manifest")

    args = parser.parse_args(argv)
    if args.command == "summary":
        return _cmd_summary()
    if args.command == "check":
        return _cmd_check(args.since)
    if args.command == "report":
        return _cmd_report(args.since)
    if args.command == "ingest":
        return _cmd_ingest(args.meeting_id)
    if args.command == "build-site":
        return _cmd_build_site()
    parser.error(f"unknown command {args.command}")
    return 2


def _cmd_summary() -> int:
    path = general.build_general_summary()
    print(f"\nWrote {path.relative_to(config.REPO_ROOT)} ({path.stat().st_size} bytes)")
    return 0


def _cmd_check(since: date | None) -> int:
    today = date.today()
    since = since or (today - timedelta(days=35))
    print(f"Checking sources for {since} → {today}...\n")
    rows = report.check_sources(since, today)
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


def _cmd_report(since: date | None) -> int:
    today = date.today()
    since = since or (today - timedelta(days=35))
    if since > today:
        print(f"error: --since {since} is in the future", file=sys.stderr)
        return 2

    print(f"Recap: {since} → {today}")
    print(f"Tracked bodies: {[b.id for b in tracked_bodies()]}")

    path = report.build_report(since=since, today=today)
    print(f"\nReport written: {path.relative_to(config.REPO_ROOT)}")
    return 0


def _cmd_ingest(meeting_id: str) -> int:
    if ":" not in meeting_id:
        print("error: meeting_id must be like source:key (e.g. diligent:1622)", file=sys.stderr)
        return 2
    source, key = meeting_id.split(":", 1)

    if source == "diligent":
        return _ingest_diligent(key)
    if source == "bccd":
        return _ingest_cd("bccd", key, bccd.list_meetings)
    if source == "swcd":
        return _ingest_cd("swcd", key, swcd.list_meetings)
    print(f"error: unknown source '{source}' (expected diligent, bccd, swcd)", file=sys.stderr)
    return 2


def _ingest_diligent(key: str) -> int:
    if not key.isdigit():
        print(f"error: diligent key must be a numeric meeting id, got '{key}'", file=sys.stderr)
        return 2
    target_id = int(key)
    meetings = diligent.list_meetings()
    ref = next((m for m in meetings if m.id == target_id), None)
    if ref is None:
        print(f"error: no Diligent meeting with id={target_id}", file=sys.stderr)
        return 1
    body = body_for_type_id(ref.type_id)
    if body is None:
        print(f"error: type_id {ref.type_id} ('{ref.type_name}') isn't in the body registry", file=sys.stderr)
        return 1
    print(f"Ingesting {ref.date} {ref.title} (body={body.id})")
    videos = report._try_list_youtube_streams()
    record = summarize.ingest_diligent(ref, body, videos=videos)
    manifest.upsert(record)
    print(f"OK  transcript={record.has_transcript}  summary={record.summary_path}")
    return 0


def _ingest_cd(source: str, key: str, lister) -> int:
    if not (key.isdigit() and len(key) == 8):
        print(f"error: {source} key must be YYYYMMDD", file=sys.stderr)
        return 2
    target = date(int(key[0:4]), int(key[4:6]), int(key[6:8]))
    body = next((b for b in tracked_bodies() if b.id == source), None)
    if body is None:
        print(f"error: {source} is not currently tracked in SCOPE.md", file=sys.stderr)
        return 1
    meeting = next((m for m in lister() if m.date == target), None)
    if meeting is None:
        print(f"error: no {source} meeting on {target}", file=sys.stderr)
        return 1
    print(f"Ingesting {source} meeting on {target}")
    record = summarize.ingest_cd(source, meeting, body)
    manifest.upsert(record)
    print(f"OK  summary={record.summary_path}")
    return 0


def _cmd_build_site() -> int:
    n_bodies, n_meetings = sitegen.build_site_content()
    print(f"Wrote {n_bodies} body page(s) and {n_meetings} meeting page(s) "
          f"to {sitegen.WEBSITE_DIR.relative_to(config.REPO_ROOT)}/")
    return 0


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got '{s}'")


if __name__ == "__main__":
    sys.exit(main())
