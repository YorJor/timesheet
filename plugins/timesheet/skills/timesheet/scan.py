#!/usr/bin/env python3
"""Summarize Claude Code activity per project per day, from the local chat history.

Usage:
  scan.py [--log-dir DIR]                          today
  scan.py [--log-dir DIR] 2026-10-07               one day
  scan.py [--log-dir DIR] 2026-10-01 2026-10-07    a range (inclusive)

--log-dir is the work log folder. Chats started there (the logging runs) are left out.

Prints JSON: for each day and project, the active hours (time ranges built from
message timestamps, idle gaps over GAP_MIN minutes split them), the chat titles,
your prompts, the files Claude edited, and your git commits that day.
Times are local. Parallel chats in one project are not double counted.
"""
import json, os, re, subprocess, sys
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

HOME = Path.home()
PROJECTS = HOME / ".claude" / "projects"
WORKLOG = None    # set from --log-dir
GAP_MIN = 15       # an idle gap longer than this ends a work block
LEAD_MIN = 5       # time credited before a block's first message (reading, typing)
PROMPT_CHARS = 200
MAX_PROMPTS = 25

def local(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()

def project_root(projdir):
    """The folder a chat was started in. Claude may cd into subfolders, so later rows drift."""
    for f in sorted(projdir.glob("*.jsonl")):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"cwd"' in line:
                        try:
                            c = json.loads(line).get("cwd")
                        except ValueError:
                            continue
                        if c:
                            return c
        except OSError:
            pass
    return None

def project_name(cwd):
    if not cwd:
        return "Unknown"
    if "/scratch-workspaces/" in cwd:
        return "No project folder"
    return Path(cwd).name or cwd

def prompt_text(msg):
    c = msg.get("content")
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        c = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(c, str) or not c.strip():
        return None
    m = re.search(r"<command-name>(.*?)</command-name>", c, re.S)
    if m:
        a = re.search(r"<command-args>(.*?)</command-args>", c, re.S)
        c = (m.group(1).strip() + " " + (a.group(1).strip() if a else "")).strip()
    elif c.lstrip().startswith(("<", "[Request interrupted", "This session is being continued", "Handoff from my previous session")):
        return None
    c = " ".join(c.split())
    return c[:PROMPT_CHARS] + ("…" if len(c) > PROMPT_CHARS else "")

def blocks(times):
    times = sorted(times)
    out, start, last = [], None, None
    for t in times:
        if start is None:
            start = last = t
        elif t - last > timedelta(minutes=GAP_MIN):
            out.append((start, last)); start = last = t
        else:
            last = t
    if start is not None:
        out.append((start, last))
    # credit lead time, then merge overlaps
    out = [(max(s - timedelta(minutes=LEAD_MIN), s.replace(hour=0, minute=0, second=0, microsecond=0)), e) for s, e in out]
    merged = []
    for s, e in sorted(out):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged

def git_commits(cwds, day):
    email = subprocess.run(["git", "config", "--global", "user.email"], capture_output=True, text=True).stdout.strip()
    repos = set()
    for cwd in cwds:
        p = Path(cwd)
        if not p.is_dir():
            continue
        top = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
        if top:
            repos.add(top); continue
        for g in list(p.glob(".git")) + list(p.glob("*/.git")) + list(p.glob("*/*/.git")):
            repos.add(str(g.parent))
    out = []
    since, until = f"{day} 00:00", f"{day + timedelta(days=1)} 00:00"
    for r in sorted(repos):
        args = ["git", "-C", r, "log", "--branches", "--remotes", "--tags", f"--since={since}", f"--until={until}", "--pretty=%ad  %s", "--date=format:%H:%M"]
        if email:
            args.append(f"--author={email}")
        res = subprocess.run(args, capture_output=True, text=True).stdout.strip()
        for line in res.splitlines():
            out.append(f"{Path(r).name}: {line}")
    return out

def scan(first, last):
    days = defaultdict(lambda: defaultdict(lambda: {"times": [], "titles": set(), "prompts": [], "files": set(), "cwds": set(), "sessions": set()}))
    lo = datetime.combine(first, datetime.min.time()).timestamp() - 86400
    roots = {}
    for f in PROJECTS.rglob("*.jsonl"):
        projdir = PROJECTS / f.relative_to(PROJECTS).parts[0]
        if projdir not in roots:
            roots[projdir] = project_root(projdir)
        root = roots[projdir]
        if f.stat().st_mtime < lo:
            continue
        titles = {}
        rows = []
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    if d.get("type") == "custom-title":
                        titles[d.get("sessionId")] = d.get("customTitle")
                    rows.append(d)
        except OSError:
            continue
        if any(d.get("type") == "user" and "<scheduled-task" in str((d.get("message") or {}).get("content", "")) for d in rows[:20]):
            continue  # scheduled task runs, such as the evening work-log update
        for d in rows:
            t, ts = d.get("type"), d.get("timestamp")
            if not ts:
                continue
            cwd = root or d.get("cwd")
            if cwd and WORKLOG and cwd.startswith(WORKLOG):
                continue  # the logging task's own chats
            if t not in ("user", "assistant") and not (t == "file-history-delta"):
                continue
            when = local(ts)
            day = when.date()
            if day < first or day > last:
                continue
            p = days[day][project_name(cwd)]
            if cwd:
                p["cwds"].add(cwd)
            sid = d.get("sessionId")
            if t == "file-history-delta":
                if d.get("trackingPath"):
                    p["files"].add(d["trackingPath"])
                continue
            p["times"].append(when)
            if sid:
                p["sessions"].add(sid)
                if titles.get(sid):
                    p["titles"].add(titles[sid])
            if t == "user" and not d.get("isMeta") and not d.get("isSidechain"):
                origin = (d.get("origin") or {}).get("kind")
                if origin in (None, "human", "composer"):
                    txt = prompt_text(d.get("message") or {})
                    if txt:
                        p["prompts"].append((when, txt))
    result = []
    for day in sorted(days):
        projects = []
        for name, p in sorted(days[day].items()):
            if not p["times"]:
                continue
            bl = blocks(p["times"])
            hours = sum((e - s).total_seconds() for s, e in bl) / 3600
            prompts = list(dict.fromkeys(f"{w:%H:%M} {txt}" for w, txt in sorted(p["prompts"])))  # resumed chats repeat history
            if len(prompts) > MAX_PROMPTS:
                step = len(prompts) / MAX_PROMPTS
                prompts = [prompts[int(i * step)] for i in range(MAX_PROMPTS)]
            projects.append({
                "project": name,
                "folders": sorted(p["cwds"]),
                "hours": round(hours, 2),
                "blocks": [f"{s:%H:%M}-{e:%H:%M}" for s, e in bl],
                "chats": len(p["sessions"]),
                "chat_titles": sorted(p["titles"]),
                "prompts": prompts,
                "files_edited": sorted(p["files"])[:40],
                "git_commits": git_commits(p["cwds"], day),
            })
        if projects:
            result.append({"date": day.isoformat(), "weekday": day.strftime("%a"), "projects": projects,
                           "total_hours": round(sum(x["hours"] for x in projects), 2)})
    return result

if __name__ == "__main__":
    a = sys.argv[1:]
    if "--log-dir" in a:
        i = a.index("--log-dir")
        WORKLOG = str(Path(os.path.expanduser(a[i + 1])).resolve())
        del a[i:i + 2]
    first = date.fromisoformat(a[0]) if a else date.today()
    last = date.fromisoformat(a[1]) if len(a) > 1 else first
    print(json.dumps({"generated": datetime.now().astimezone().isoformat(timespec="minutes"),
                      "gap_minutes": GAP_MIN, "days": scan(first, last)}, ensure_ascii=False, indent=1))
