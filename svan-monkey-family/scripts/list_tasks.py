#!/usr/bin/env python3
"""List every ticket in .tasks/todo in claim order, condensed for scheduling.

For each ticket prints: file name, front matter, H1 title, the "Refs" section,
other ticket numbers it mentions (dependency hints) and the file paths it names
(conflict hints).  Order = the order svan-monkey would claim them (st_ctime,
i.e. the time the file was added to .tasks/todo).

Usage (from the project's main directory):
    list_tasks.py [--tasks-dir .tasks] [--json]
Exits 2 when the queue is empty.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TICKET_REF_RE = re.compile(r"(?<![\w/.-])#?(\d{3})(?=[\s)\]:,.;-]|$)")
PATH_RE = re.compile(r"`([^`\s]+/[^`\s]+|[^`\s]+\.[A-Za-z]{1,5})`")
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def split_front_matter(text: str):
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for raw in lines[1:i]:
                if ":" in raw and not raw.startswith((" ", "\t", "#")):
                    k, _, v = raw.partition(":")
                    fm[k.strip().lower()] = v.strip().strip("\"'")
            return fm, "\n".join(lines[i + 1:])
    return {}, text


def sections(body: str):
    out = {}
    matches = list(SECTION_RE.finditer(body))
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        out[m.group(1).strip().lower()] = body[m.end():end].strip()
    return out


def own_number(name: str, fm: dict):
    m = re.match(r"(\d{3})", name)
    if m:
        return m.group(1)
    t = fm.get("ticket", "")
    return t.zfill(3) if t.isdigit() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks-dir", default=".tasks")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    todo = Path(args.tasks_dir) / "todo"
    if not todo.is_dir():
        print(f"error: {todo} does not exist (run svan-init)", file=sys.stderr)
        return 1
    files = sorted((p for p in todo.glob("*.md") if p.is_file()),
                   key=lambda p: p.stat().st_ctime)
    if not files:
        print("error: no tasks in .tasks/todo", file=sys.stderr)
        return 2

    # Only numbers that belong to an existing ticket count as mentions; this
    # keeps line numbers and other 3-digit values out of the dependency hints.
    known = set()
    for folder in ("backlog", "todo", "doing", "done", "archive"):
        for q in (Path(args.tasks_dir) / folder).glob("*.md"):
            m = re.match(r"(\d{3})", q.name)
            if m:
                known.add(m.group(1))

    tickets = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, body = split_front_matter(text)
        h1 = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), "")
        secs = sections(body)
        num = own_number(p.name, fm)
        refs = sorted({n for n in TICKET_REF_RE.findall(body)
                       if n != num and n in known})
        paths = []
        for m in PATH_RE.findall(body):
            if m not in paths:
                paths.append(m)
        tickets.append({
            "file": str(p),
            "number": num,
            "title": fm.get("title") or h1,
            "front_matter": fm,
            "refs_section": secs.get("refs", ""),
            "mentions": refs,
            "paths": paths,
            "words": len(body.split()),
        })

    if args.json:
        print(json.dumps(tickets, indent=2, ensure_ascii=False))
        return 0

    print(f"# {len(tickets)} ticket(s) in {todo}, claim order\n")
    for i, t in enumerate(tickets, 1):
        print(f"## {i}. {Path(t['file']).name}")
        print(f"- title: {t['title']}")
        if t["front_matter"]:
            fm = ", ".join(f"{k}={v}" for k, v in t["front_matter"].items()
                           if k not in ("title",))
            if fm:
                print(f"- front matter: {fm}")
        print(f"- length: ~{t['words']} words")
        if t["mentions"]:
            print(f"- mentions tickets: {', '.join(t['mentions'])}")
        if t["refs_section"]:
            refs = " / ".join(l.strip(" -*") for l in t["refs_section"].splitlines() if l.strip())
            print(f"- refs: {refs[:300]}")
        if t["paths"]:
            print(f"- paths named: {', '.join(t['paths'][:25])}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
