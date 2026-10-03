#!/usr/bin/env python3
"""Render wally's status page: one self-contained HTML file, rewritten every few
minutes by status-snapshot.timer and served by status-serve.service. Stdlib
only, so it runs under the system python without the repo's venv. Every
section is collected independently — a failed probe shows "unknown" and never
takes the page down."""
from __future__ import annotations

import glob
import html
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(os.environ.get("WIRE_STATUS_DIR", "/var/lib/wire-status"))
REPO = Path(os.environ.get("WIRE_REPO", Path(__file__).resolve().parent.parent))
SITE = os.environ.get("WIRE_STATUS_SITE", "https://belviderewire.com")
TUNNEL_UNIT = os.environ.get("WIRE_STATUS_TUNNEL_UNIT", "cloudflared.service")
TUNNEL_URL = os.environ.get("WIRE_STATUS_TUNNEL_URL", "https://list.belviderewire.com/subscription/form")
LISTMONK_URL = os.environ.get("WIRE_STATUS_LISTMONK_URL", "http://localhost:9000/admin/login")
DB_CONTAINER = os.environ.get("LISTMONK_DB_CONTAINER", "listmonk_db")
BACKUP_DIR = Path(os.environ.get("LISTMONK_BACKUP_DIR", "/opt/listmonk/backups"))
ALERT_URL = os.environ.get("WIRE_ALERT_URL", "")

OURS = ("belvidere-wire.timer", "listmonk-backup.timer")
HISTORY_KEEP = 7 * 24 * 12  # a week at one run per five minutes
STALE_AFTER_MIN = 15
BACKUP_MAX_AGE_H = 26
BAD_RUNS_BEFORE_ALERT = 2

OK, WARN, BAD, UNK = "ok", "warn", "bad", "unk"
MARK = {OK: "✓", WARN: "!", BAD: "✕", UNK: "?"}
PILL = {OK: "OK", WARN: "CHECK", BAD: "DOWN", UNK: "UNKNOWN"}


class H(str):
    """Already-escaped HTML."""


def esc(v) -> str:
    return v if isinstance(v, H) else html.escape(str(v))


class Section:
    def __init__(self, key, title, wide=False, alert=True):
        self.key, self.title, self.wide, self.alert = key, title, wide, alert
        self.rows = []
        self.extra = []
        self.error = None

    def add(self, label, value, status=None):
        self.rows.append((label, value, status))

    @property
    def status(self):
        if self.error:
            return UNK
        sts = [r[2] for r in self.rows if r[2]]
        for st in (BAD, WARN, UNK):
            if st in sts:
                return st
        return OK

    def reason(self):
        if self.error:
            return self.error
        for label, value, st in self.rows:
            if st == BAD:
                return f"{label}: {value}"
        return ""


def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return p.returncode, p.stdout


def probe(url, timeout=10):
    t = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "wally-status/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        return None, None, str(e)
    return code, int((time.monotonic() - t) * 1000), None


def fmt_dur(sec):
    sec = int(abs(sec))
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, r = divmod(r, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m"
    return f"{r}s"


def ago(ts):
    return fmt_dur(time.time() - ts) + " ago"


def until(ts):
    return "in " + fmt_dur(ts - time.time())


def fmt_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_when(ts):
    return time.strftime("%a %b %d %H:%M", time.localtime(ts))


def parse_ts(s):
    m = re.search(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})", s or "")
    if not m:
        return None
    return time.mktime(time.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S"))


def prop_blocks(out):
    blocks = []
    for chunk in out.strip().split("\n\n"):
        d = dict(l.split("=", 1) for l in chunk.splitlines() if "=" in l)
        if d:
            blocks.append(d)
    return blocks


def bar(pct, status):
    return H(f'<span class="bar"><i class="st-{status}" style="width:{min(max(pct, 0), 100):.0f}%"></i></span>')


def by_pct(pct, warn, bad):
    return BAD if pct >= bad else WARN if pct >= warn else OK


# ---------------------------------------------------------------- collectors


def host(s, ctx):
    up = float(Path("/proc/uptime").read_text().split()[0])
    s.add("Uptime", f"{fmt_dur(up)} (booted {fmt_when(time.time() - up)})")
    l1, l5, l15 = os.getloadavg()
    cpus = os.cpu_count() or 1
    ctx["load"] = l1
    s.add("Load 1 / 5 / 15 min", f"{l1:.2f} / {l5:.2f} / {l15:.2f} on {cpus} cores",
          BAD if l5 > 2 * cpus else WARN if l5 > cpus else OK)

    temps = []
    for f in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            temps.append(int(Path(f).read_text()) / 1000)
        except (OSError, ValueError):
            pass
    if temps:
        t = max(temps)
        s.add("CPU temperature", f"{t:.0f} °C", BAD if t >= 85 else WARN if t >= 75 else OK)

    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                s.add("OS", line.split("=", 1)[1].strip('"'))
    except OSError:
        pass

    if Path("/var/run/reboot-required").exists():
        s.add("Reboot", "required to finish an update", WARN)
    rc, out = run(["apt", "list", "--upgradable"], timeout=30)
    if rc == 0:
        n = sum(1 for l in out.splitlines() if "upgradable" in l)
        s.add("Package updates", f"{n} pending", WARN if n >= 25 else None)


def memory(s, ctx):
    m = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0]) * 1024
    total, avail = m["MemTotal"], m["MemAvailable"]
    used = total - avail
    pct = used / total * 100
    ctx["mem"] = pct
    st = by_pct(pct, 85, 95)
    s.add("RAM", H(f"{bar(pct, st)} {fmt_bytes(used)} of {fmt_bytes(total)} ({pct:.0f}%)"), st)
    s.add("Available", fmt_bytes(avail))
    s.add("Cache + buffers", fmt_bytes(m.get("Cached", 0) + m.get("Buffers", 0)))
    stot = m.get("SwapTotal", 0)
    if stot:
        sused = stot - m.get("SwapFree", 0)
        spct = sused / stot * 100
        sst = by_pct(spct, 50, 90)
        s.add("Swap", H(f"{bar(spct, sst)} {fmt_bytes(sused)} of {fmt_bytes(stot)}"), sst)
    else:
        s.add("Swap", "none")


def disk(s, ctx):
    real = {"ext4", "ext3", "xfs", "btrfs", "vfat", "zfs", "f2fs", "exfat", "ntfs", "fuseblk"}
    seen = set()
    for line in Path("/proc/mounts").read_text().splitlines():
        dev, mnt, fs = line.split()[:3]
        if fs not in real or dev in seen or "/var/lib/docker" in mnt:
            continue
        seen.add(dev)
        u = shutil.disk_usage(mnt)
        pct = u.used / (u.used + u.free) * 100
        if mnt == "/":
            ctx["disk"] = pct
        st = by_pct(pct, 80, 92)
        s.add(mnt, H(f"{bar(pct, st)} {fmt_bytes(u.used)} of {fmt_bytes(u.used + u.free)} ({pct:.0f}%)"), st)
    rc, out = run(["docker", "system", "df", "--format", "{{json .}}"])
    if rc == 0:
        for line in out.splitlines():
            d = json.loads(line)
            s.add(f"Docker {d['Type'].lower()}", f"{d['Size']} ({d['Reclaimable']} reclaimable)")


def network(s, ctx):
    iface = None
    for line in Path("/proc/net/route").read_text().splitlines()[1:]:
        f = line.split()
        if f[1] == "00000000":
            iface = f[0]
            break
    if not iface:
        s.add("Default route", "none", BAD)
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 53))
        ip = sock.getsockname()[0]
    finally:
        sock.close()
    s.add("Interface", f"{iface} · {ip}")

    rx = tx = None
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, rest = line.split(":", 1)
        if name.strip() == iface:
            f = rest.split()
            rx, tx = int(f[0]), int(f[8])
    if rx is not None:
        ctx["net"] = {"iface": iface, "rx": rx, "tx": tx}
        s.add("Since boot", f"↓ {fmt_bytes(rx)} · ↑ {fmt_bytes(tx)}")
        p = ctx["prev"]
        if p and p.get("iface") == iface and "rx" in p and rx >= p["rx"] and tx >= p["tx"]:
            dt = ctx["now"] - p["t"]
            if dt > 0:
                ctx["net"]["bps"] = ((rx - p["rx"]) + (tx - p["tx"])) / dt
                s.add("Last interval", f"↓ {fmt_bytes((rx - p['rx']) / dt)}/s · ↑ {fmt_bytes((tx - p['tx']) / dt)}/s")

    t = time.monotonic()
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=5).close()
        s.add("Internet (1.1.1.1:443)", f"reachable, {int((time.monotonic() - t) * 1000)} ms", OK)
    except OSError as e:
        s.add("Internet (1.1.1.1:443)", f"unreachable ({e})", BAD)
    t = time.monotonic()
    host_name = re.sub(r"^https?://", "", SITE).split("/")[0]
    try:
        socket.getaddrinfo(host_name, 443)
        s.add("DNS", f"{host_name} resolves, {int((time.monotonic() - t) * 1000)} ms", OK)
    except OSError as e:
        s.add("DNS", f"{host_name} failed ({e})", BAD)
    code, ms, err = probe(SITE + "/")
    if code == 200:
        s.add("Public site", f"HTTP 200, {ms} ms", OK)
    else:
        s.add("Public site", err or f"HTTP {code}", BAD if code is None or code >= 500 else WARN)


def tunnel(s, ctx):
    rc, out = run(["systemctl", "show", TUNNEL_UNIT, "-p", "ActiveState,SubState,ActiveEnterTimestamp,NRestarts"])
    p = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
    state = f"{p.get('ActiveState', '?')} ({p.get('SubState', '?')})"
    s.add("Service", f"{TUNNEL_UNIT}: {state}", OK if p.get("SubState") == "running" else BAD)
    since = parse_ts(p.get("ActiveEnterTimestamp"))
    if since and p.get("ActiveState") == "active":
        s.add("Up for", fmt_dur(time.time() - since))
    try:
        n = int(p.get("NRestarts", 0))
    except ValueError:
        n = 0
    s.add("Auto-restarts", str(n), WARN if n >= 3 else OK)

    rc, out = run(["journalctl", "-u", TUNNEL_UNIT, "--since", "1 hour ago", "-o", "cat", "--no-pager", "-q"])
    if rc == 0:
        errs = [l for l in out.splitlines() if re.search(r"\bERR\b", l)]
        s.add("Errors, last hour", str(len(errs)), WARN if errs else OK)
        if errs:
            s.extra.append(H(f'<p class="log">{esc(errs[-1][:200])}</p>'))
    else:
        s.add("Errors, last hour", "journal not readable", UNK)

    code, ms, err = probe(TUNNEL_URL)
    if code == 200:
        s.add("End to end", f"{TUNNEL_URL.split('/')[2]} answers through the tunnel, {ms} ms", OK)
    elif code in (502, 503, 504, 530) or code is None:
        s.add("End to end", err or f"HTTP {code} — the edge cannot reach the origin", BAD)
    else:
        s.add("End to end", f"HTTP {code} (unexpected, but the edge answered)", WARN)


def psql(sql):
    return run(["docker", "exec", DB_CONTAINER, "psql", "-U", "listmonk", "-d", "listmonk",
                "-At", "-F", "|", "-c", sql])


def listmonk(s, ctx):
    code, ms, err = probe(LISTMONK_URL)
    s.add("App", f"login page HTTP 200, {ms} ms" if code == 200 else err or f"HTTP {code}", OK if code == 200 else BAD)

    rc, out = run(["docker", "inspect", "-f", "{{.State.Status}} {{.RestartCount}}", DB_CONTAINER])
    if rc != 0:
        s.add("Database", f"container {DB_CONTAINER} not found", BAD)
        return
    state, restarts = out.split()
    s.add("Database", f"{DB_CONTAINER}: {state}", OK if state == "running" else BAD)
    if state != "running":
        return

    rc, out = psql("select count(*) from subscribers")
    if rc != 0:
        s.add("Postgres", "query failed", BAD)
        return
    s.add("Postgres", "answering queries", OK)
    s.add("Subscribers", out.strip())
    rc, out = psql("select subscription_status, count(*) from subscriber_lists group by 1 order by 1")
    counts = dict(l.split("|") for l in out.splitlines() if "|" in l)
    s.add("Subscriptions", " · ".join(f"{k} {v}" for k, v in counts.items()) or "none")
    ctx["subs"] = int(counts.get("confirmed", 0))
    rc, out = psql("select count(*) from lists")
    s.add("Lists", out.strip())
    rc, out = psql("select pg_size_pretty(pg_database_size('listmonk'))")
    s.add("Database size", out.strip())
    rc, out = psql("select name, status, sent, to_send, coalesce(extract(epoch from started_at)::bigint, 0) "
                   "from campaigns order by id desc limit 1")
    if out.strip():
        name, status, sent, to_send, started = out.strip().rsplit("|", 4)
        when = f", {ago(int(started))}" if int(started) else ""
        s.add("Last campaign", f"{name} — {status}, {sent}/{to_send} sent{when}")
    else:
        s.add("Last campaign", "none yet")


def backups(s, ctx):
    files = sorted(BACKUP_DIR.glob("listmonk-*.dump"), key=lambda p: p.stat().st_mtime)
    if not files:
        s.add("Dumps", f"none in {BACKUP_DIR}", BAD)
        return
    newest = files[-1].stat()
    age_h = (time.time() - newest.st_mtime) / 3600
    s.add("Newest dump", f"{files[-1].name} · {ago(newest.st_mtime)}", BAD if age_h > BACKUP_MAX_AGE_H else OK)
    s.add("Size", fmt_bytes(newest.st_size), BAD if newest.st_size == 0 else OK)
    s.add("Retained", f"{len(files)} dumps, {fmt_bytes(sum(f.stat().st_size for f in files))} total")
    s.add("Oldest", ago(files[0].stat().st_mtime))
    s.add("Off the box", "no copy leaves wally (see ops/README.md)", None)


def pipeline(s, ctx):
    g = ["git", "-C", str(REPO)]
    rc, out = run(g + ["status", "--porcelain"])
    if rc != 0:
        s.add("Clone", f"cannot read {REPO}", UNK)
        return
    dirty = [l for l in out.splitlines() if l.strip()]
    s.add("Working tree", f"{len(dirty)} uncommitted paths — the Monday run refuses to start" if dirty else "clean",
          BAD if dirty else OK)
    rc, out = run(g + ["log", "-1", "--format=%h|%ct|%s"])
    head = run(g + ["rev-parse", "HEAD"])[1].strip()
    if rc == 0:
        sha, ct, subj = out.strip().split("|", 2)
        s.add("Checked out", f"{sha} {subj[:60]} ({ago(int(ct))})")
    rc, out = run(g + ["ls-remote", "origin", "refs/heads/main"], timeout=30)
    if rc != 0 or not out.strip():
        s.add("origin", "cannot reach — the Monday push would fail", WARN)
    else:
        remote = out.split()[0]
        s.add("origin/main", "matches the checkout" if remote == head else "ahead of the checkout (next run pulls it)")

    pages = [int(p.stem) for p in (REPO / "website" / "_front_pages").glob("*.md") if p.stem.isdigit()]
    if pages:
        n = max(pages)
        code, ms, err = probe(f"{SITE}/issues/{n:03d}/")
        s.add(f"Issue No. {n}", "live" if code == 200 else err or f"HTTP {code} (deploy may still be building)",
              OK if code == 200 else WARN)

    rc, out = run(["systemctl", "show", "belvidere-wire.service", "-p",
                   "ActiveState,Result,ExecMainStartTimestamp,ExecMainExitTimestamp"])
    p = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
    start, end = parse_ts(p.get("ExecMainStartTimestamp")), parse_ts(p.get("ExecMainExitTimestamp"))
    if p.get("ActiveState") in ("active", "activating"):
        s.add("Monday run", "running now", OK)
    elif not start:
        s.add("Monday run", "has not run yet")
    else:
        ok = p.get("Result") == "success"
        dur = f", took {fmt_dur(end - start)}" if end and end > start else ""
        s.add("Monday run", f"{p.get('Result')} {ago(end or start)}{dur}", OK if ok else BAD)


def containers(s, ctx):
    rc, out = run(["docker", "ps", "-a", "-q"])
    if rc != 0:
        s.add("Docker", "not reachable", UNK)
        return
    ids = out.split()
    rows = []
    worst = OK
    fmt = "{{.Name}}|{{.State.Status}}|{{.RestartCount}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.Config.Image}}"
    rc, out = run(["docker", "inspect", "-f", fmt] + ids) if ids else (0, "")
    for line in out.splitlines():
        name, state, restarts, health, image = line.split("|", 4)
        st = OK
        if state != "running":
            st = WARN
        if health == "unhealthy":
            st = BAD
        elif int(restarts) >= 5 and st == OK:
            st = WARN
        shown = state + (f" ({health})" if health else "")
        rows.append([name.lstrip("/"), image, (shown, st), restarts])
        worst = BAD if BAD in (worst, st) else WARN if WARN in (worst, st) else worst
    s.add("Containers", f"{len(rows)} total", worst)
    s.extra.append(table(["Name", "Image", "State", "Restarts"], rows))


def timers(s, ctx):
    entries = {}
    rc, out = run(["systemctl", "list-timers", "--all", "--output=json", "--no-pager"])
    data = None
    if rc == 0:
        try:
            data = json.loads(out)
        except ValueError:
            pass
    if data is not None:
        for e in data:
            entries[e["unit"]] = ((e.get("next") or 0) / 1e6 or None, (e.get("last") or 0) / 1e6 or None,
                                  e.get("activates"))
    else:
        rc, out = run(["systemctl", "list-units", "--type=timer", "--all", "--plain", "--no-legend", "--no-pager"])
        units = [l.split()[0] for l in out.splitlines() if l.strip()]
        for b in prop_blocks(run(["systemctl", "show", "-p", "Id,Unit,NextElapseUSecRealtime,LastTriggerUSec"]
                                 + units)[1]):
            entries[b["Id"]] = (parse_ts(b.get("NextElapseUSecRealtime")), parse_ts(b.get("LastTriggerUSec")),
                                b.get("Unit"))
    if not entries:
        s.add("Timers", "could not list", UNK)
        return

    svcs = sorted({a for _, _, a in entries.values() if a})
    results = {b["Id"]: b for b in prop_blocks(run(["systemctl", "show", "-p", "Id,Result,ActiveState"] + svcs)[1])}

    s.add("Timers", f"{len(entries)} on this box")
    for t in OURS:
        if t not in entries:
            s.add(t, "not installed", BAD)
        elif not entries[t][0]:
            s.add(t, "not scheduled — enable it", BAD)

    far = float("inf")
    order = sorted(entries, key=lambda u: (u not in OURS, entries[u][0] or far))
    rows = []
    for unit in order:
        nxt, last, svc = entries[unit]
        r = results.get(svc, {})
        if r.get("ActiveState") in ("active", "activating"):
            res = ("running", OK)
        elif not last:
            res = ("—", None)
        elif r.get("Result") == "success":
            res = ("ok", OK)
        else:
            res = (f"failed: {r.get('Result', '?')}", BAD if unit in OURS else WARN)
            s.add(f"{svc} last run", r.get("Result", "?"), res[1])
        name = unit.replace(".timer", "")
        rows.append([H(f"<b>{esc(name)}</b>") if unit in OURS else name,
                     f"{fmt_when(nxt)} ({until(nxt)})" if nxt else "—",
                     ago(last) if last else "—", res])
    s.extra.append(table(["Timer", "Next run", "Last run", "Result"], rows))


# --------------------------------------------------------------------- trends


def downsample(values, buckets=168):
    if len(values) <= buckets:
        return values
    size = -(-len(values) // buckets)
    out = []
    for i in range(0, len(values), size):
        chunk = [v for v in values[i:i + size] if v is not None]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


def spark(values, lo=None, hi=None, w=240, h=36):
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return "collecting data"
    lo = min(vals) if lo is None else lo
    hi = max(vals) if hi is None else hi
    if hi == lo:
        hi = lo + 1
    step = w / (len(values) - 1)
    pts = [f"{i * step:.1f},{h - 2 - (v - lo) / (hi - lo) * (h - 4):.1f}"
           for i, v in enumerate(values) if v is not None]
    return H(f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" aria-label="trend">'
             f'<polyline points="{" ".join(pts)}" fill="none" stroke="currentColor" stroke-width="1.5" '
             f'vector-effect="non-scaling-stroke"/></svg>')


def trends(s, history):
    if len(history) < 2:
        s.add("History", "collecting — charts appear after a few runs")
        return
    s.add("Window", f"last {fmt_dur(history[-1]['t'] - history[0]['t'])}, {len(history)} samples")
    for label, key, fmt, lo, hi in (
        ("Memory used", "mem", lambda v: f"{v:.0f}%", 0, 100),
        ("Root disk used", "disk", lambda v: f"{v:.0f}%", 0, 100),
        ("Load (1 min)", "load", lambda v: f"{v:.2f}", 0, None),
        ("Network (↓+↑)", "bps", lambda v: fmt_bytes(v) + "/s", 0, None),
        ("Confirmed subscribers", "subs", lambda v: f"{v:.0f}", None, None),
    ):
        raw = [e.get(key) for e in history]
        vals = [v for v in raw if v is not None]
        if len(vals) < 2:
            continue
        line = spark(downsample(raw), lo, hi)
        s.add(label, H(f'<span class="trend">{line}</span> <span class="range">now {esc(fmt(vals[-1]))} · '
                       f'min {esc(fmt(min(vals)))} · max {esc(fmt(max(vals)))}</span>'))


# ------------------------------------------------------------------ rendering


def cell(c):
    if isinstance(c, tuple):
        text, st = c
        return f'<td class="st-{st}">{MARK[st]} {esc(text)}</td>' if st else f"<td>{esc(text)}</td>"
    return f"<td>{esc(c)}</td>"


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(cell(c) for c in r) + "</tr>" for r in rows)
    return H(f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def render_section(s):
    st = s.status
    rows = []
    for label, value, rst in s.rows:
        cls = f' class="st-{rst}"' if rst else ""
        mark = f'<span class="mark" aria-hidden="true">{MARK[rst]}</span> ' if rst and rst != OK else ""
        rows.append(f"<div><dt>{esc(label)}</dt><dd{cls}>{mark}{esc(value)}</dd></div>")
    if s.error:
        rows.append(f'<div><dt>Error</dt><dd class="st-unk">{esc(s.error)}</dd></div>')
    wide = " wide" if s.wide else ""
    return (f'<section class="card{wide}"><h2>{esc(s.title)}<span class="pill st-{st}">{PILL[st]}</span></h2>'
            f'<dl>{"".join(rows)}</dl>{"".join(s.extra)}</section>')


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#5d6470;--line:#e2e5ea;--ok:#177a3c;--warn:#a55b00;--bad:#c4281c;--unk:#6b7280;--okbg:#e5f4ea;--warnbg:#fdf0dc;--badbg:#fbe5e3;--unkbg:#eceef1}
@media (prefers-color-scheme:dark){:root{--bg:#101215;--card:#181b20;--ink:#e8eaee;--mute:#9aa1ad;--line:#2a2f37;--ok:#4cc27a;--warn:#e8a34a;--bad:#ff6b5e;--unk:#9aa1ad;--okbg:#15301f;--warnbg:#3a2a12;--badbg:#3d1a17;--unkbg:#23272e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}
header{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline;justify-content:space-between;margin:8px 0 12px}
h1{font-size:22px;margin:0}
.when{color:var(--mute);font-size:13px}
.banner{padding:12px 16px;border-radius:8px;font-weight:600;margin-bottom:16px}
.banner.st-ok{background:var(--okbg);color:var(--ok)}.banner.st-warn,.banner.st-unk{background:var(--warnbg);color:var(--warn)}.banner.st-bad{background:var(--badbg);color:var(--bad)}
#stale{background:var(--badbg);color:var(--bad);padding:10px 16px;border-radius:8px;margin-bottom:16px;font-weight:600}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(min(100%,360px),1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0}
.card.wide{grid-column:1/-1}
h2{font-size:15px;margin:0 0 10px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.pill{font-size:11px;letter-spacing:.04em;padding:2px 8px;border-radius:99px;font-weight:700}
.pill.st-ok{background:var(--okbg)}.pill.st-warn{background:var(--warnbg)}.pill.st-bad{background:var(--badbg)}.pill.st-unk{background:var(--unkbg)}
.st-ok{color:var(--ok)}.st-warn{color:var(--warn)}.st-bad{color:var(--bad)}.st-unk{color:var(--unk)}
dl{margin:0}dl>div{display:grid;grid-template-columns:minmax(90px,38%) 1fr;gap:8px;padding:5px 0;border-top:1px solid var(--line)}
dl>div:first-child{border-top:0}
dt{color:var(--mute)}dd{margin:0;overflow-wrap:anywhere}
dd:not([class]),dd.st-ok{color:var(--ink)}
.mark{font-weight:700}
.bar{display:inline-block;width:90px;height:8px;border-radius:4px;background:var(--line);vertical-align:middle;margin-right:6px;overflow:hidden}
.bar i{display:block;height:100%;background:currentColor}
.log{font:12px ui-monospace,monospace;color:var(--mute);margin:8px 0 0;overflow-wrap:anywhere}
.tablewrap{overflow-x:auto;margin-top:8px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:5px 10px 5px 0;border-top:1px solid var(--line);white-space:nowrap}
th{color:var(--mute);font-weight:600;border-top:0}
.trend{display:inline-block;width:240px;max-width:100%;vertical-align:middle;color:var(--mute)}
.spark{width:100%;height:36px;display:block}
.range{color:var(--mute);font-size:13px;display:block}
footer{color:var(--mute);font-size:13px;margin:20px 0}
"""

SCRIPT = """
var g=%d*1000,a=document.getElementById('age'),st=document.getElementById('stale');
function tick(){var m=Math.floor((Date.now()-g)/60000);a.textContent=m<1?'just now':m+' min ago';st.hidden=m<%d}
tick();setInterval(tick,30000);
"""


def render(sections, now):
    sts = [s.status for s in sections]
    overall = BAD if BAD in sts else WARN if WARN in sts else UNK if UNK in sts else OK
    flagged = [s.title for s in sections if s.status != OK]
    if overall == OK:
        text = "All systems normal"
    elif overall == UNK:
        text = "Could not check: " + ", ".join(flagged)
    else:
        text = "Needs attention: " + ", ".join(flagged)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300"><title>wally status</title>
<style>{CSS}</style></head><body><main>
<header><h1>wally</h1><span class="when">Updated {esc(time.strftime("%a %b %d, %H:%M %Z", time.localtime(now)))} · <span id="age"></span></span></header>
<div id="stale" hidden>This page has not been refreshed for over {STALE_AFTER_MIN} minutes — status-snapshot.timer may have stopped.</div>
<div class="banner st-{overall}">{esc(text)}</div>
<div class="grid">{"".join(render_section(s) for s in sections)}</div>
<footer>Written by ops/status-snapshot.py every five minutes. LAN only.</footer>
</main><script>{SCRIPT % (int(now), STALE_AFTER_MIN)}</script></body></html>
"""


# ---------------------------------------------------------------- state, alerts


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_atomic(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def post_alert(title, body):
    if not ALERT_URL:
        return
    req = urllib.request.Request(ALERT_URL, data=body.encode(), headers={"Title": title})
    try:
        urllib.request.urlopen(req, timeout=15).close()
    except Exception as e:
        print(f"warning: alert POST failed: {e}")


def notify(state, sections):
    # Pipeline and Timers are left out: a failed Monday run already alerts
    # through belvidere-wire-failure@, and would otherwise arrive three times.
    for s in sections:
        if not s.alert:
            continue
        cur = state.setdefault(s.key, {"bad_runs": 0, "alerted": False})
        if s.status == BAD:
            cur["bad_runs"] += 1
            if cur["bad_runs"] >= BAD_RUNS_BEFORE_ALERT and not cur["alerted"]:
                cur["alerted"] = True
                post_alert(f"wally: {s.title} is down", s.reason())
        elif s.status == OK:
            if cur["alerted"]:
                post_alert(f"wally: {s.title} recovered", "Back to normal.")
            cur["bad_runs"], cur["alerted"] = 0, False


SPECS = (
    ("host", "Host", host, False, True),
    ("memory", "Memory", memory, False, True),
    ("disk", "Disk", disk, False, True),
    ("network", "Network", network, False, True),
    ("tunnel", "Cloudflare tunnel", tunnel, False, True),
    ("listmonk", "Listmonk", listmonk, False, True),
    ("backups", "Listmonk backups", backups, False, True),
    ("pipeline", "Publishing pipeline", pipeline, False, False),
    ("containers", "Containers", containers, False, True),
    ("timers", "Timers", timers, True, False),
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    now = time.time()
    history = load_json(OUT / "history.json", [])
    state = load_json(OUT / "state.json", {})
    ctx = {"prev": history[-1] if history else None, "now": now}

    sections = []
    for key, title, fn, wide, alert in SPECS:
        s = Section(key, title, wide, alert)
        try:
            fn(s, ctx)
        except Exception as e:
            s.error = f"{type(e).__name__}: {e}"
        sections.append(s)

    entry = {"t": now}
    for k in ("mem", "disk", "load", "subs"):
        if k in ctx:
            entry[k] = ctx[k]
    if "net" in ctx:
        entry.update(iface=ctx["net"]["iface"], rx=ctx["net"]["rx"], tx=ctx["net"]["tx"])
        if "bps" in ctx["net"]:
            entry["bps"] = ctx["net"]["bps"]
    history = (history + [entry])[-HISTORY_KEEP:]

    t = Section("trends", "Trends", wide=True, alert=False)
    try:
        trends(t, history)
    except Exception as e:
        t.error = f"{type(e).__name__}: {e}"
    sections.append(t)

    write_atomic(OUT / "history.json", json.dumps(history, separators=(",", ":")))
    write_atomic(OUT / "index.html", render(sections, now))
    notify(state, sections)
    write_atomic(OUT / "state.json", json.dumps(state))


if __name__ == "__main__":
    main()
