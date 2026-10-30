#!/usr/bin/env python3
"""Collect everything needed to check whether backlog tickets are already done.

Prints one markdown document with three parts so an LLM can compare without
opening every file itself:

  1. Backlog tickets  – full text (optionally truncated), one block per ticket
  2. Done tickets     – compact: title, date, problem/scope excerpt, history tail
  3. Recent commits   – hash, date, subject, body, changed files

Plus cross-reference hints: done tickets and commits that literally mention a
backlog ticket's number (e.g. "Ticket 034", "#34", "(ticket 034)").  Hints are
only hints – the semantic comparison is the LLM's job.

Usage (run from the project's main directory):
    collect.py [--tasks-dir .tasks] [--commits 20] [--backlog-chars 0]
               [--done-excerpt 320] [--body-chars 600] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

FINISHED_KEYS = ("finished", "finished_at", "completed", "completed_at", "done_at", "done")
PROBLEM_SECTIONS = ("problem", "overview", "kontext", "context")
SCOPE_SECTIONS = ("scope", "scope / acceptance criteria", "acceptance criteria", "umfang", "ziel", "goal")
HISTORY_SECTIONS = ("history", "verlauf", "ergebnis", "result")
REFS_SECTIONS = ("refs", "referenzen", "references")

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
TICKET_NO_RE = re.compile(r"^(\d+)[-_ ]")


# --------------------------------------------------------------------------- parsing (shared with recap.py)


def split_front_matter(text: str):
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
                fm[key.strip().lower()] = value.strip().strip('"').strip("'")
            return fm, "\n".join(lines[i + 1 :])
    return {}, text


def parse_sections(body: str):
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
    h = re.sub(r"\(.*?\)", "", h)
    h = re.sub(r"[^a-zäöüß/& ]+", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def find_section(sections: Dict[str, str], names) -> Optional[str]:
    for name in names:
        for key, text in sections.items():
            if key == name or key.startswith(name + " ") or key.startswith(name + "/") or key.startswith(name + " /"):
                if text:
                    return text
    return None


def flatten(text: Optional[str], limit: int) -> str:
    """Whole section flattened to one line (code blocks dropped), truncated."""
    if not text:
        return ""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^#{3,}\s+", "", text, flags=re.M)
    text = re.sub(r"\[(x| )\]\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "• ", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    return shorten(text, limit)


def last_items(text: Optional[str], n: int, limit: int) -> List[str]:
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


def ticket_number(name: str) -> Optional[int]:
    m = TICKET_NO_RE.match(name)
    return int(m.group(1)) if m else None


def mention_re(number: int) -> re.Pattern:
    """Matches 'Ticket 034', 'ticket-34', '#034', 'Task 34' – not bare numbers.

    Whitespace must stay on one line (so a heading "…Ticket" followed by a
    list item "1." does not match) and the '#' form needs at least two digits
    (so "Risiko #1" does not match)."""
    word = rf"\b(?:ticket|task|aufgabe)[ \t]*[-#_]?[ \t]*0*{number}\b"
    hash_ = rf"#(?=\d{{2,}})0*{number}\b"
    return re.compile(rf"(?:{word}|{hash_})", re.I)


# --------------------------------------------------------------------------- loading


def load_backlog(tasks_dir: Path, max_chars: int) -> List[dict]:
    out = []
    d = tasks_dir / "backlog"
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, body = split_front_matter(text)
        title, sections = parse_sections(body)
        out.append({
            "file": p.name,
            "path": str(p),
            "number": ticket_number(p.name),
            "title": title or p.stem,
            "text": shorten(text.strip(), max_chars),
            "chars": len(text.strip()),
        })
    return out


def load_done(tasks_dir: Path, excerpt: int) -> List[dict]:
    out = []
    d = tasks_dir / "done"
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, body = split_front_matter(text)
        title, sections = parse_sections(body)
        finished = None
        for k in FINISHED_KEYS:
            if fm.get(k):
                m = DATE_RE.search(fm[k])
                if m:
                    finished = m.group(0)
                    break
        out.append({
            "file": p.name,
            "path": str(p),
            "number": ticket_number(p.name),
            "title": title or p.stem,
            "finished": finished,
            "problem": flatten(find_section(sections, PROBLEM_SECTIONS), excerpt),
            "scope": flatten(find_section(sections, SCOPE_SECTIONS), excerpt),
            "refs": flatten(find_section(sections, REFS_SECTIONS), excerpt // 2),
            "history_tail": last_items(find_section(sections, HISTORY_SECTIONS), 2, excerpt // 2),
            "_text": text,
        })
    return out


def load_commits(project_root: Path, n: int, body_chars: int) -> List[dict]:
    sep = "\x1e"
    fmt = f"%H{sep}%h{sep}%cs{sep}%an{sep}%s{sep}%b{sep}"
    try:
        res = subprocess.run(
            ["git", "log", f"-{n}", f"--format=%x1d{fmt}", "--name-status", "--no-merges"],
            cwd=str(project_root), capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"warning: git log failed: {e}", file=sys.stderr)
        return []
    if res.returncode != 0:
        print(f"warning: git log failed: {res.stderr.strip()}", file=sys.stderr)
        return []
    commits = []
    for chunk in res.stdout.split("\x1d"):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        parts = chunk.split(sep)
        if len(parts) < 7:
            continue
        full, short, cdate, author, subject, body, rest = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
        files = []
        for line in rest.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^([A-Z])\d*\t(.+?)(?:\t(.+))?$", line)
            if m:
                status, path, new = m.groups()
                files.append(f"{status} {new or path}")
        commits.append({
            "hash": short,
            "full": full,
            "date": cdate,
            "author": author,
            "subject": subject.strip(),
            "body": shorten(re.sub(r"\n{3,}", "\n\n", body.strip()), body_chars),
            "files": files,
        })
    return commits


# --------------------------------------------------------------------------- hints


def build_hints(backlog: List[dict], done: List[dict], commits: List[dict]) -> Dict[str, dict]:
    hints: Dict[str, dict] = {}
    for b in backlog:
        n = b["number"]
        if n is None:
            continue
        rx = mention_re(n)
        in_done = [d["file"] for d in done if rx.search(d["_text"])]
        in_commits = [c["hash"] for c in commits if rx.search(c["subject"] + "\n" + c["body"])]
        touched = [c["hash"] for c in commits if any(b["file"] in f for f in c["files"])]
        if in_done or in_commits or touched:
            hints[b["file"]] = {"done_mentions": in_done, "commit_mentions": in_commits, "file_touched_in": touched}
    return hints


# --------------------------------------------------------------------------- output


def render(backlog, done, commits, hints, archive_count: int, tasks_dir: Path, n_commits: int) -> str:
    out: List[str] = []
    out.append(f"# svan backlog-cleanup — {tasks_dir.resolve().parent.name}")
    out.append(f"Stand {date.today().isoformat()} · backlog: {len(backlog)} · done: {len(done)} · "
               f"archive: {archive_count} · commits geladen: {len(commits)} (angefragt {n_commits})")
    out.append("")

    out.append("## Hinweise (wörtliche Erwähnungen der Backlog-Ticketnummern)")
    if not hints:
        out.append("_keine wörtlichen Erwähnungen gefunden – rein semantisch vergleichen_")
    for f, h in hints.items():
        bits = []
        if h["done_mentions"]:
            bits.append("in done: " + ", ".join(h["done_mentions"]))
        if h["commit_mentions"]:
            bits.append("in commits: " + ", ".join(h["commit_mentions"]))
        if h["file_touched_in"]:
            bits.append("Ticketdatei selbst geändert in: " + ", ".join(h["file_touched_in"]))
        out.append(f"- `{f}` → " + " · ".join(bits))
    out.append("")

    out.append("## Done-Tickets (kompakt)")
    if not done:
        out.append("_keine erledigten Tickets_")
    for d in done:
        meta = f" · fertig {d['finished']}" if d["finished"] else ""
        out.append(f"### {d['title']}")
        out.append(f"`done/{d['file']}`{meta}")
        if d["problem"]:
            out.append(f"- Problem: {d['problem']}")
        if d["scope"]:
            out.append(f"- Scope: {d['scope']}")
        if d["history_tail"]:
            out.append(f"- History (Ende): {' / '.join(d['history_tail'])}")
        if d["refs"]:
            out.append(f"- Refs: {d['refs']}")
        out.append("")

    out.append(f"## Letzte {len(commits)} Commits (ohne Merges)")
    if not commits:
        out.append("_keine Commits gefunden (kein git-Repo?)_")
    for c in commits:
        out.append(f"### {c['hash']} · {c['date']} · {c['subject']}")
        if c["body"]:
            out.append(c["body"])
        if c["files"]:
            shown = c["files"][:40]
            more = f" … (+{len(c['files']) - 40} weitere)" if len(c["files"]) > 40 else ""
            out.append("Dateien: " + ", ".join(f"`{f}`" for f in shown) + more)
        out.append("")

    out.append("## Backlog-Tickets (Volltext)")
    if not backlog:
        out.append("_backlog ist leer_")
    for b in backlog:
        trunc = f" · gekürzt von {b['chars']} Zeichen" if len(b["text"]) < b["chars"] else ""
        out.append(f"<!-- ===== backlog/{b['file']}{trunc} ===== -->")
        out.append(b["text"])
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks-dir", default=".tasks")
    ap.add_argument("--commits", type=int, default=20, help="number of recent commits (default: 20)")
    ap.add_argument("--backlog-chars", type=int, default=0,
                    help="truncate each backlog ticket to this many chars (default 0 = full text)")
    ap.add_argument("--done-excerpt", type=int, default=320, help="chars per done-ticket excerpt (default: 320)")
    ap.add_argument("--body-chars", type=int, default=600, help="chars per commit body (default: 600)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    tasks_dir = Path(args.tasks_dir)
    if not tasks_dir.is_dir():
        print(f"error: {tasks_dir} does not exist – run svan-init first", file=sys.stderr)
        return 1
    project_root = tasks_dir.resolve().parent

    backlog = load_backlog(tasks_dir, args.backlog_chars)
    if not backlog:
        print("error: .tasks/backlog is empty – nothing to clean up", file=sys.stderr)
        return 2
    done = load_done(tasks_dir, args.done_excerpt)
    commits = load_commits(project_root, args.commits, args.body_chars)
    hints = build_hints(backlog, done, commits)
    archive_dir = tasks_dir / "archive"
    archive_count = len(list(archive_dir.glob("*.md"))) if archive_dir.is_dir() else 0

    if args.json:
        for d in done:
            d.pop("_text", None)
        print(json.dumps({"backlog": backlog, "done": done, "commits": commits, "hints": hints,
                          "_meta": {"project": project_root.name, "archive_count": archive_count,
                                    "generated": date.today().isoformat()}},
                         ensure_ascii=False, indent=2))
    else:
        print(render(backlog, done, commits, hints, archive_count, tasks_dir, args.commits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
