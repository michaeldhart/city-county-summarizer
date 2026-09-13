"""YouTube channel + captions via yt-dlp.

Which tab holds the meetings varies by channel: the county archives live
streams (/streams), other channels upload to /videos. Jurisdiction.youtube_tab
picks it.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    title: str


def _run_ytdlp(*args: str) -> str:
    proc = subprocess.run(
        ["python3", "-m", "yt_dlp", *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {proc.stderr.strip()}")
    return proc.stdout


def list_videos(channel_id: str, tab: str = "streams", limit: int = 200) -> list[YouTubeVideo]:
    """Enumerate a channel tab's videos, newest first."""
    url = f"https://www.youtube.com/channel/{channel_id}/{tab}"
    out = _run_ytdlp(
        "--flat-playlist",
        "--playlist-end", str(limit),
        "--print", "%(id)s\t%(title)s",
        url,
    )
    videos: list[YouTubeVideo] = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        vid, title = line.split("\t", 1)
        videos.append(YouTubeVideo(video_id=vid, title=title))
    return videos


# Meeting-type keywords in a YouTube title — YouTube titles are informal
# (e.g. "Boone County COTW-Finance 6/12/2025"), separate from Diligent's clean type IDs.
_TITLE_HINTS: dict[str, tuple[str, ...]] = {
    "board":         (r"boone county board(?!\s*of\s*health)",),
    "cotw-admin":    (r"cotw[- ]*admin", r"committee of the whole.*admin"),
    "cotw-finance":  (r"cotw[- ]*finance", r"committee of the whole.*finance"),
}


def find_video(videos: list[YouTubeVideo], meeting_date: date, body_id: str) -> YouTubeVideo | None:
    """Best-effort match: date somewhere in the title + a body-hint keyword."""
    hints = _TITLE_HINTS.get(body_id)
    if not hints:
        return None
    date_patterns = _date_patterns(meeting_date)
    for v in videos:
        t = v.title.lower()
        if not any(re.search(h, t) for h in hints):
            continue
        if any(dp in t for dp in date_patterns):
            return v
    return None


def _date_patterns(d: date) -> list[str]:
    """YouTube titles use several date formats — normalize to lowercase substrings."""
    return [
        f"{d.month}/{d.day}/{d.year}",           # 4/16/2026
        f"{d.month:02d}/{d.day:02d}/{d.year}",   # 04/16/2026
        f"{d.month:02d}{d.day:02d}{d.year}",     # 04162026
        f"{d.month}-{d.day}-{d.year}",           # 4-16-2026
    ]


def download_captions(video_id: str, dest_dir: Path) -> Path | None:
    """Fetch English auto-captions as VTT. Returns the file path, or None if unavailable."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest_dir / "video.%(ext)s")
    try:
        _run_ytdlp(
            "--write-auto-sub", "--sub-lang", "en", "--sub-format", "vtt",
            "--skip-download",
            "--extractor-args", "youtube:player_client=android",
            "-o", outtmpl,
            f"https://www.youtube.com/watch?v={video_id}",
        )
    except RuntimeError:
        return None
    vtt = dest_dir / "video.en.vtt"
    return vtt if vtt.exists() else None


def vtt_to_text(vtt_path: Path) -> str:
    """Clean YouTube VTT into readable text: strip timestamps, word tags, entities, dedupe dupes."""
    lines: list[str] = []
    for ln in vtt_path.read_text().splitlines():
        if ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if not ln.strip():
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}\.\d+ -->", ln):
            continue
        ln = re.sub(r"<[^>]+>", "", ln)
        ln = ln.replace("&gt;&gt;", ">>").replace("&amp;", "&").strip()
        if ln:
            lines.append(ln)
    out: list[str] = []
    for ln in lines:
        if not out or out[-1] != ln:
            out.append(ln)
    return "\n".join(out)
