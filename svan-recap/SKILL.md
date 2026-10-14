---
description: Recap of the current project, based on upcoming and past svan tasks.
disable-model-invocation: true
---

Run `scripts/recap.py` (resolve the path relative to this skill's directory) with `python3` from the project's main directory. The script scans `.tasks/{backlog,todo,doing,done}`, parses every ticket's YAML header, title and sections, and prints a condensed markdown board — do NOT read all ticket files yourself; the script output is your primary source.

Pass any arguments the user gave along to the script (`$ARGUMENTS`). Useful flags:
- `--done N` — number of most recently finished tickets (default 10)
- `--since DAYS` — instead: every ticket finished in the last DAYS days
- `--all-done` — every finished ticket
- `--excerpt CHARS` — length of the per-ticket excerpts (default 280)
- `--json` — machine-readable output

If the script exits non-zero because `.tasks` does not exist, tell the user and suggest running svan-init; stop there.

From the script output write the recap for the user, in the language the tickets are written in (usually German). Structure:

1. **Was zuletzt passiert ist** — summarise the recently finished tickets, grouped by theme (not ticket by ticket). Name the ticket numbers per theme, mention the finish dates range and, if available, the rough total time / tokens.
2. **In Arbeit** — tickets in `doing`, with their checkbox progress and the last history entry.
3. **Als nächstes** — the `todo` queue in claim order (this is the order svan-next will pick them).
4. **Geplante Themen (Backlog)** — cluster the backlog tickets into topics and give one line per topic with the ticket numbers. Point out obvious dependencies or tickets that look stale/superseded by finished work.

Keep it tight: a recap, not a list. Only open an individual ticket file if a detail from the excerpt is genuinely unclear and matters for the recap.
