#!/usr/bin/env python3
"""Move a backlog ticket to .tasks/archive and record why.

Inserts a status note right below the ticket's H1 title (after any YAML front
matter), following the convention already used for archived tickets:

    > **Status: ARCHIVIERT (2026-10-14)** — Bereits umgesetzt.
    >
    > **Begründung:** <reason>

Then moves the file to .tasks/archive/ and prints the new path.  Refuses to
overwrite an existing file in the archive.

Usage (run from the project's main directory):
    archive.py .tasks/backlog/034-foo.md --reason "Umgesetzt in Commit abc123 (components/Foo.tsx) …"
               [--label "Bereits umgesetzt."] [--tasks-dir .tasks] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


def build_note(label: str, reason: str) -> str:
    reason_lines = [l.rstrip() for l in reason.strip().splitlines()] or [""]
    body = "\n".join(("> " + l).rstrip() for l in reason_lines)
    # first reason line gets the bold prefix
    body = body.replace("> ", "> **Begründung:** ", 1)
    return f"> **Status: ARCHIVIERT ({date.today().isoformat()})** — {label}\n>\n{body}\n"


def insert_note(text: str, note: str) -> str:
    lines = text.splitlines(keepends=True)
    i = 0
    # skip YAML front matter
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    # find the H1 title after the front matter
    for j in range(i, len(lines)):
        if lines[j].startswith("# "):
            i = j + 1
            break
    else:
        # no H1: put the note at the very top of the body
        pass
    head = "".join(lines[:i])
    tail = "".join(lines[i:])
    if head and not head.endswith("\n"):
        head += "\n"
    return head + "\n" + note + ("\n" + tail.lstrip("\n") if tail.strip() else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticket", help="path of the backlog ticket to archive")
    ap.add_argument("--reason", required=True, help="why the ticket is archived (where/how it was implemented)")
    ap.add_argument("--label", default="Bereits umgesetzt.", help="short status label (default: 'Bereits umgesetzt.')")
    ap.add_argument("--tasks-dir", default=".tasks")
    ap.add_argument("--dry-run", action="store_true", help="print the resulting file instead of writing/moving")
    args = ap.parse_args(argv)

    src = Path(args.ticket)
    if not src.is_file():
        print(f"error: {src} is not a file", file=sys.stderr)
        return 1
    archive = Path(args.tasks_dir) / "archive"
    dst = archive / src.name
    if dst.exists():
        print(f"error: {dst} already exists", file=sys.stderr)
        return 3

    text = src.read_text(encoding="utf-8", errors="replace")
    new_text = insert_note(text, build_note(args.label, args.reason))

    if args.dry_run:
        print(new_text)
        print(f"--- dry run: would move {src} -> {dst}", file=sys.stderr)
        return 0

    archive.mkdir(parents=True, exist_ok=True)
    src.write_text(new_text, encoding="utf-8")
    src.rename(dst)
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
