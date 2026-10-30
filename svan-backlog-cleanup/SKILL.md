---
description: Checks backlog tickets against done tickets and recent commits; offers to archive tickets that are already implemented.
disable-model-invocation: true
---

Run `scripts/collect.py` (resolve the path relative to this skill's directory) with `python3` from the project's main directory. Pass any arguments the user gave along (`$ARGUMENTS`). Useful flags: `--commits N` (default 20), `--backlog-chars N` (truncate long backlog tickets, default = full text), `--done-excerpt N`, `--json`.

The script prints one document: literal number-mention hints, every done ticket in compact form, the last 20 commits (subject, body, changed files) and the full text of every backlog ticket. This output is your primary source — do NOT read all ticket files yourself. If the script exits non-zero because `.tasks` is missing, tell the user and suggest svan-init; if the backlog is empty, say so. Stop there in both cases.

Then work through the backlog in two passes. Answer in the language the tickets are written in (usually German).

**Pass 1 — done tickets.** For every backlog ticket decide whether a done ticket (or a combination of done tickets) already covers its scope. Compare semantically — problem, acceptance criteria, touched files — not by title. The "Hinweise" section lists literal mentions of the backlog ticket's number; treat these as leads, not proof: a done ticket may mention a backlog ticket only to declare it out of scope. Classify each backlog ticket as *fully covered*, *partially covered* (name which criteria remain) or *not covered*. Only a *fully covered* ticket counts as done in this pass.

**Pass 2 — commits.** For every backlog ticket that is not fully covered by done tickets, check whether the last 20 commits implemented it anyway (commits without a ticket, or ticket work that was folded into another ticket's commit). Use subject, body and the changed-file list. When a commit looks like a match, verify it in the code before claiming anything: run `git show --stat <hash>` / `git show <hash> -- <file>` or grep the working tree, and note concrete `file:line` locations. A commit message alone is not sufficient evidence.

**Asking the user.** For every ticket you consider done (from pass 1 or pass 2), ask the user individually with AskUserQuestion, one question per ticket, in backlog order. The question must contain a short justification: which done ticket(s) or commit(s) implemented it, in which files/functions, and how — two to four sentences, with the ticket numbers / short hashes and `file:line` refs. If the coverage is only partial, say which acceptance criteria are still open. Offer these options:

1. **Archivieren** — move the ticket to `.tasks/archive`.
2. **Im Backlog behalten** — leave the ticket untouched.
3. **Behalten, Hinweis eintragen** — keep the ticket but append a short "Stand"-note (what is already implemented, what remains) under the title, so the ticket can be slimmed down later.

Never archive without an explicit "Archivieren" answer. Do not ask about tickets you consider *not covered*; list them in the final summary instead.

**Archiving.** For each "Archivieren" answer run `scripts/archive.py <path> --reason "<justification>"` from the project's main directory. The reason is the same justification you showed the user (plain text, may span lines; name ticket numbers, commit hashes and files). The script inserts the `> **Status: ARCHIVIERT (date)** — Bereits umgesetzt.` note below the title, following the convention of existing archived tickets, moves the file to `.tasks/archive/` and prints the new path. It refuses to overwrite; if it fails, report the error and leave the ticket where it is. For "Behalten, Hinweis eintragen" edit the ticket yourself: insert a blockquote `> **Stand YYYY-MM-DD:** …` below the title. Do not commit anything unless the user asks.

**Summary.** Finish with a short overview: tickets archived (with the implementing ticket/commit), tickets kept with a note, tickets kept unchanged, and tickets that are clearly still open. Point out backlog tickets that look partially done or superseded even if you did not ask about them.
