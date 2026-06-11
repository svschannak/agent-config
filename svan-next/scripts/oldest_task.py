#!/usr/bin/env python3
"""Atomically claim the oldest markdown task from .tasks/todo.

"Oldest" is determined by the file's status-change time (st_ctime), which on
macOS/Linux is updated when a file is moved into a directory. This reflects
when the task was added to .tasks/todo rather than when it was originally
created.

The oldest task is moved from .tasks/todo to .tasks/doing in a single step so it
cannot be skipped or claimed twice, and the new path in .tasks/doing is printed.
Exits non-zero (without moving anything) if the queue is empty.
"""

import sys
from pathlib import Path


def main() -> int:
    todo = Path(".tasks/todo")
    doing = Path(".tasks/doing")
    if not todo.is_dir():
        print(f"error: {todo} does not exist", file=sys.stderr)
        return 1

    candidates = [p for p in todo.glob("*.md") if p.is_file()]
    if not candidates:
        print("error: no tasks in .tasks/todo", file=sys.stderr)
        return 2

    oldest = min(candidates, key=lambda p: p.stat().st_ctime)

    doing.mkdir(parents=True, exist_ok=True)
    target = doing / oldest.name
    if target.exists():
        print(f"error: {target} already exists", file=sys.stderr)
        return 3

    oldest.rename(target)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
