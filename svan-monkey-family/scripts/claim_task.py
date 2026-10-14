#!/usr/bin/env python3
"""Atomically claim specific tickets from .tasks/todo into .tasks/doing.

    claim_task.py 034-foo.md 036-bar.md     # claim these (name or path)
    claim_task.py                           # claim the oldest one

Each file is moved with a single rename so it cannot be claimed twice.  Prints
the new path per ticket.  Refuses (non-zero, nothing moved for that file) when
a ticket is missing from todo or already exists in doing.
"""

import sys
from pathlib import Path


def main(argv) -> int:
    todo, doing = Path(".tasks/todo"), Path(".tasks/doing")
    if not todo.is_dir():
        print(f"error: {todo} does not exist", file=sys.stderr)
        return 1
    names = [Path(a).name for a in argv]
    if not names:
        candidates = [p for p in todo.glob("*.md") if p.is_file()]
        if not candidates:
            print("error: no tasks in .tasks/todo", file=sys.stderr)
            return 2
        names = [min(candidates, key=lambda p: p.stat().st_ctime).name]

    doing.mkdir(parents=True, exist_ok=True)
    rc = 0
    for name in names:
        src, dst = todo / name, doing / name
        if not src.is_file():
            print(f"error: {src} not found", file=sys.stderr)
            rc = 3
            continue
        if dst.exists():
            print(f"error: {dst} already exists", file=sys.stderr)
            rc = 3
            continue
        src.rename(dst)
        print(dst)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
