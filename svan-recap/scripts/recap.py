#!/usr/bin/env python3
"""Compact recap of a project's svan task board (.tasks/{backlog,todo,doing,done}).

Collects every markdown ticket, parses the optional YAML front matter, the
title and the sections, and prints a condensed overview so an LLM does not
have to read every ticket in full:

  * done     – the N most recently finished tickets (newest first)
  * doing    – tickets currently claimed
  * todo     – the queue, in the order svan-next will claim it (oldest first)
  * backlog  – planned topics, with a short excerpt each

Front matter keys are tolerant: finished/finished_at/completed/done_at,
started/started_at/created_at, total_time/duration/time, tokens/used_tokens/
tokens_used, status, result, phase.  The "finished" date of a done ticket is
taken from the front matter, else from the last git commit touching the file,
else from the file's modification time.

Usage (run from the project's main directory):
    recap.py [--tasks-dir .tasks] [--done 10] [--since DAYS]
             [--excerpt 280] [--all-done] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

FOLDERS = ("backlog", "todo", "doing", "done")

FINISHED_KEYS = ("finished", "finished_at", "completed", "completed_at", "done_at", "done")
STARTED_KEYS = ("started", "started_at", "created_at", "created")
TIME_KEYS = ("total_time", "duration", "time", "total_duration")
TOKEN_KEYS = ("tokens", "used_tokens", "tokens_used", "total_tokens")

# Section names (lowercased, digits stripped) whose first paragraph is worth
# showing.  Order = display priority.
PROBLEM_SECTIONS = ("problem", "overview", "kontext", "context")
GOAL_SECTIONS = ("ziel", "goal", "auswirkung", "impact", "outcome", "ergebnis", "result")
RESULT_SECTIONS = ("history", "verlauf", "ergebnis", "result", "status")

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
CHECKBOX_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[( |x|X)\]", re.M)


# --------------------------------------------------------------------------- parsing


def split_front_matter(text: str):
    """Return (front_matter_dict, body)."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm: Dict[str, str] = {}
            for raw in lines[1:i]:
                if ":" not in raw or raw.startswith((" ", "\t", "#")):
                    continue
                key, _, value = raw.partition(":")
                value = value.strip().strip('"').strip("'")
                fm[key.strip().lower()] = value
            return fm, "\n".join(lines[i + 1 :])
    return {}, text


def first_value(fm: Dict[str, str], keys) -> Optional[str]:
    for k in keys:
        v = fm.get(k)
        if v:
            return v
    return None


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    m = DATE_RE.search(value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_sections(body: str):
    """Return (title, {section_name_normalised: section_text})."""
    title = None
    sections: Dict[str, str] = {}
    current = None
    buf: List[str] = []
    in_code = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("# ") and title is None:
            title = line[2:].strip()
            continue
        if not in_code and line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = normalise_heading(line[3:])
            buf = []
            continue
        buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return title, sections


def normalise_heading(h: str) -> str:
    h = h.lower()
    h = re.sub(r"\(.*?\)", "", h)  # "Plan (bestätigt 2026-09-10)" -> "plan"
    h = re.sub(r"[^a-zäöüß/& ]+", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def find_section(sections: Dict[str, str], names) -> Optional[str]:
    for name in names:
        for key, text in sections.items():
            if key == name or key.startswith(name + " ") or key.startswith(name + "/") or key.startswith(name + " /"):
                if text:
                    return text
    return None


def first_paragraph(text: Optional[str], limit: int) -> str:
    """First paragraph of a section, flattened and truncated."""
    if not text:
        return ""
    paras = re.split(r"\n\s*\n", text.strip())
    para = ""
    for p in paras:
        p = p.strip()
        if p and not p.startswith("```") and not p.startswith("### "):
            para = p
            break
    para = re.sub(r"^#{3,}\s+.*$", "", para, flags=re.M)
    para = re.sub(r"\[(x| )\]\s*", "", para, flags=re.I)
    para = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", para, flags=re.M)  # list markers
    para = re.sub(r"\s+", " ", para).strip()
    return shorten(para, limit)


def last_items(text: Optional[str], n: int, limit: int) -> List[str]:
    """Last n list items (or paragraphs) of a section such as History.

    Wrapped continuation lines are joined to their item so excerpts do not
    start mid-sentence."""
    if not text:
        return []
    items: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        is_item = re.match(r"^(?:[-*+]|\d+[.)])\s+", line) is not None
        if is_item or not items:
            items.append(re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", line))
        else:
            items[-1] += " " + line
    return [shorten(re.sub(r"\s+", " ", i), limit) for i in items[-n:]]


def shorten(s: str, limit: int) -> str:
    if limit <= 0 or len(s) <= limit:
        return s
    cut = s[: limit - 1]
    if " " in cut[limit // 2 :]:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


def checkbox_progress(body: str):
    boxes = CHECKBOX_RE.findall(body)
    if not boxes:
        return None
    done = sum(1 for b in boxes if b.lower() == "x")
    return done, len(boxes)


# --------------------------------------------------------------------------- git / fs


def git_last_commit_date(path: Path, cwd: Path) -> Optional[date]:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return parse_date(out.stdout.strip())


def mtime_date(path: Path) -> date:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone().date()


# --------------------------------------------------------------------------- model


def load_ticket(path: Path, folder: str, excerpt: int, project_root: Path, use_git: bool) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = split_front_matter(text)
    title, sections = parse_sections(body)
    st = path.stat()

    finished = parse_date(first_value(fm, FINISHED_KEYS))
    finished_source = "front-matter" if finished else None
    if folder == "done" and finished is None and use_git:
        finished = git_last_commit_date(path, project_root)
        finished_source = "git" if finished else None
    if folder == "done" and finished is None:
        finished = mtime_date(path)
        finished_source = "mtime"

    ticket = {
        "file": path.name,
        "path": str(path),
        "folder": folder,
        "title": title or path.stem,
        "status": fm.get("status"),
        "phase": fm.get("phase"),
        "started": (parse_date(first_value(fm, STARTED_KEYS)) or None),
        "finished": finished,
        "finished_source": finished_source,
        "total_time": first_value(fm, TIME_KEYS),
        "tokens": first_value(fm, TOKEN_KEYS),
        "result": fm.get("result"),
        "problem": first_paragraph(find_section(sections, PROBLEM_SECTIONS), excerpt),
        "goal": first_paragraph(find_section(sections, GOAL_SECTIONS), excerpt),
        "history_tail": last_items(find_section(sections, ("history", "verlauf")), 2, excerpt),
        "progress": checkbox_progress(body),
        "sections": sorted(sections.keys()),
        "queued_at": datetime.fromtimestamp(st.st_ctime).astimezone().isoformat(timespec="minutes"),
        "ctime": st.st_ctime,
        "size": st.st_size,
    }
    return ticket


def collect(tasks_dir: Path, excerpt: int, use_git: bool) -> Dict[str, List[dict]]:
    project_root = tasks_dir.resolve().parent
    board: Dict[str, List[dict]] = {}
    for folder in FOLDERS:
        d = tasks_dir / folder
        tickets = []
        if d.is_dir():
            for p in sorted(d.glob("*.md")):
                if p.is_file():
                    tickets.append(load_ticket(p, folder, excerpt, project_root, use_git))
        board[folder] = tickets
    board["done"].sort(key=lambda t: (t["finished"] or date.min, t["ctime"]), reverse=True)
    board["todo"].sort(key=lambda t: t["ctime"])  # same order svan-next claims
    board["doing"].sort(key=lambda t: t["ctime"])
    return board


# --------------------------------------------------------------------------- output


def fmt_meta(t: dict) -> str:
    bits = []
    if t["finished"]:
        bits.append(f"fertig {t['finished'].isoformat()}")
    if t["total_time"]:
        bits.append(f"Zeit {shorten(t['total_time'], 40)}")
    if t["tokens"]:
        bits.append(f"Tokens {shorten(t['tokens'], 30)}")
    if t["phase"]:
        bits.append(f"Phase {shorten(t['phase'], 40)}")
    return " · ".join(bits)


def render_markdown(board: Dict[str, List[dict]], args, tasks_dir: Path, total_done: int) -> str:
    out: List[str] = []
    counts = " · ".join(f"{f}: {len(board[f]) if f != 'done' else total_done}" for f in FOLDERS)
    out.append(f"# svan recap — {tasks_dir.resolve().parent.name}")
    out.append(f"Stand {date.today().isoformat()} · {counts}")
    out.append("")

    # ---- done
    done = board["done"]
    if args.since:
        label = f"letzte {args.since} Tage"
    elif args.all_done:
        label = "alle"
    else:
        label = f"letzte {min(args.done, total_done)} von {total_done}"
    out.append(f"## Zuletzt erledigt ({label})")
    if not done:
        out.append("_keine erledigten Tickets_")
    for t in done:
        out.append(f"### {t['title']}")
        out.append(f"`done/{t['file']}` · {fmt_meta(t)}")
        if t["result"]:
            out.append(f"- Ergebnis: {shorten(t['result'], args.excerpt)}")
        if t["problem"]:
            out.append(f"- Problem: {t['problem']}")
        if t["goal"]:
            out.append(f"- Ziel/Auswirkung: {t['goal']}")
        if t["history_tail"]:
            out.append(f"- History (Ende): {' / '.join(t['history_tail'])}")
        out.append("")

    # ---- doing
    out.append("## In Arbeit (doing)")
    if not board["doing"]:
        out.append("_nichts in Arbeit_")
    for t in board["doing"]:
        prog = f" · Fortschritt {t['progress'][0]}/{t['progress'][1]} Checkboxen" if t["progress"] else ""
        out.append(f"- **{t['title']}** `doing/{t['file']}`{prog}")
        if t["problem"]:
            out.append(f"  - Problem: {t['problem']}")
        if t["history_tail"]:
            out.append(f"  - History (Ende): {' / '.join(t['history_tail'])}")
    out.append("")

    # ---- todo
    out.append("## Als nächstes (todo, in Claim-Reihenfolge)")
    if not board["todo"]:
        out.append("_todo ist leer_")
    for i, t in enumerate(board["todo"], 1):
        out.append(f"{i}. **{t['title']}** `todo/{t['file']}`")
        if t["problem"]:
            out.append(f"   - Problem: {t['problem']}")
        if t["goal"]:
            out.append(f"   - Ziel: {t['goal']}")
    out.append("")

    # ---- backlog
    out.append("## Backlog (geplante Themen)")
    if not board["backlog"]:
        out.append("_backlog ist leer_")
    for t in board["backlog"]:
        out.append(f"- **{t['title']}** `backlog/{t['file']}`")
        if t["problem"]:
            out.append(f"  - Problem: {t['problem']}")
        if t["goal"]:
            out.append(f"  - Ziel: {t['goal']}")
    out.append("")
    return "\n".join(out)


def to_jsonable(board: Dict[str, List[dict]]) -> dict:
    def conv(t: dict) -> dict:
        t = dict(t)
        for k in ("started", "finished"):
            t[k] = t[k].isoformat() if t[k] else None
        t.pop("ctime", None)
        return t

    return {f: [conv(t) for t in ts] for f, ts in board.items()}


# --------------------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks-dir", default=".tasks", help="task board directory (default: .tasks)")
    ap.add_argument("--done", type=int, default=10, help="number of recent done tickets to show (default: 10)")
    ap.add_argument("--since", type=int, default=None, metavar="DAYS",
                    help="instead of --done: show done tickets finished within the last DAYS days")
    ap.add_argument("--all-done", action="store_true", help="show every done ticket")
    ap.add_argument("--excerpt", type=int, default=280, help="max characters per excerpt (default: 280)")
    ap.add_argument("--no-git", action="store_true", help="do not ask git for finish dates")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = ap.parse_args(argv)

    tasks_dir = Path(args.tasks_dir)
    if not tasks_dir.is_dir():
        print(f"error: {tasks_dir} does not exist – run svan-init first", file=sys.stderr)
        return 1

    board = collect(tasks_dir, args.excerpt, use_git=not args.no_git)
    total_done = len(board["done"])
    if args.since:
        cutoff = date.today() - timedelta(days=args.since)
        board["done"] = [t for t in board["done"] if t["finished"] and t["finished"] >= cutoff]
    elif not args.all_done:
        board["done"] = board["done"][: args.done]

    if args.json:
        payload = to_jsonable(board)
        payload["_meta"] = {"project": tasks_dir.resolve().parent.name, "total_done": total_done,
                            "generated": date.today().isoformat()}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(board, args, tasks_dir, total_done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
