"""Command-line entry point.

Commands:
  ccs summary                           rebuild general_summary.md
  ccs report                            monthly report (default: last 35 days recap, next 30 days lookahead)
  ccs report --since YYYY-MM-DD --until YYYY-MM-DD
  ccs ingest boarddocs:<unique>         re-ingest a specific meeting, updating the manifest
  ccs ingest bccd:YYYYMMDD
  ccs ingest swcd:YYYYMMDD
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from . import bccd, boarddocs, config, general, manifest, report, summarize, swcd, youtube
from .config import body_for_title, load_env, tracked_bodies


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(prog="ccs", description="Boone County meeting monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", help="Rebuild the general_summary.md living doc")

    p_report = sub.add_parser("report", help="Generate a monthly report")
    p_report.add_argument("--since", type=_parse_date, default=None,
                          help="Recap window start (default: 35 days ago)")
    p_report.add_argument("--until", type=_parse_date, default=None,
                          help="Lookahead window end (default: today + 30 days)")

    p_ingest = sub.add_parser("ingest", help="Force-ingest a specific meeting")
    p_ingest.add_argument("meeting_id", help="e.g. boarddocs:DSCKED517FD7, bccd:20260420, swcd:20260701")

    args = parser.parse_args(argv)
    if args.command == "summary":
        return _cmd_summary()
    if args.command == "report":
        return _cmd_report(args.since, args.until)
    if args.command == "ingest":
        return _cmd_ingest(args.meeting_id)
    parser.error(f"unknown command {args.command}")
    return 2


def _cmd_summary() -> int:
    path = general.build_general_summary()
    print(f"\nWrote {path.relative_to(config.REPO_ROOT)} ({path.stat().st_size} bytes)")
    return 0


def _cmd_report(since: date | None, until: date | None) -> int:
    today = date.today()
    since = since or (today - timedelta(days=35))
    until = until or (today + timedelta(days=30))
    if since > today:
        print(f"error: --since {since} is in the future", file=sys.stderr)
        return 2
    if until < today:
        print(f"error: --until {until} is in the past", file=sys.stderr)
        return 2

    print(f"Recap: {since} → {today}")
    print(f"Lookahead: {today} → {until}")
    print(f"Tracked bodies: {[b.id for b in tracked_bodies()]}")

    path = report.build_report(since=since, until=until, today=today)
    print(f"\nReport written: {path.relative_to(config.REPO_ROOT)}")
    return 0


def _cmd_ingest(meeting_id: str) -> int:
    if ":" not in meeting_id:
        print("error: meeting_id must be like source:key (e.g. boarddocs:DSCKED517FD7)", file=sys.stderr)
        return 2
    source, key = meeting_id.split(":", 1)

    if source == "boarddocs":
        return _ingest_boarddocs(key)
    if source == "bccd":
        return _ingest_cd("bccd", key, bccd.list_meetings)
    if source == "swcd":
        return _ingest_cd("swcd", key, swcd.list_meetings)
    print(f"error: unknown source '{source}' (expected boarddocs, bccd, swcd)", file=sys.stderr)
    return 2


def _ingest_boarddocs(unique: str) -> int:
    meetings = boarddocs.list_meetings()
    ref = next((m for m in meetings if m.unique == unique), None)
    if ref is None:
        print(f"error: no BoardDocs meeting with unique={unique}", file=sys.stderr)
        return 1
    body = body_for_title(ref.title)
    if body is None:
        print(f"error: title '{ref.title}' didn't match any body", file=sys.stderr)
        return 1
    print(f"Ingesting {ref.date} {ref.title} (body={body.id})")
    videos = report._try_list_youtube_streams()
    record = summarize.ingest_boarddocs(ref, body, videos=videos)
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


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got '{s}'")


if __name__ == "__main__":
    sys.exit(main())
