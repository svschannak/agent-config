---
description: Processes ALL tasks from .tasks/todo autonomously — groups the tickets into sequential lanes that can run in parallel, runs one svan-monkey worker per lane in its own git worktree, merges the lane branches and reports
disable-model-invocation: true
---

svan-monkey-family is the batch variant of svan-monkey: it empties `.tasks/todo` instead of taking a single ticket. You are the orchestrator. You do not implement tickets yourself — you plan the schedule, spawn one worker per lane, merge their branches, keep `main` green and report. The workers follow the svan-monkey procedure as written in `WORKER.md` next to this file. Nobody asks the user anything: not you, not the workers. Decide, document, continue; do not stop because the run takes long.

Arguments (`$ARGUMENTS`): a bare number sets the maximum number of parallel lanes (default 3). `--dry-run` stops after presenting the schedule without claiming or changing anything.

## 1. Inventory and preconditions

Run `scripts/list_tasks.py` (resolve the path relative to this skill's directory) with `python3` from the project's main directory. It prints every ticket in `.tasks/todo` in claim order with title, front matter, the tickets it mentions and the file paths it names. If it reports an empty queue (non-zero exit), tell the user there are no tasks and stop.

Check, and stop with a clear message if any fails (this is a stop, not a question):

- The project is a git repository and the working tree is clean (`git status --porcelain` shows nothing except untracked files outside `.tasks`). Parallel worktrees on top of uncommitted changes are not safe.
- Note the current branch and HEAD. Note whether `.tasks` is tracked (`git ls-files .tasks | head -1` prints something) — this decides where the workers find their ticket files (step 3).
- Tickets already in `.tasks/doing` are not part of this run; leave them alone and mention them in the final report.
- Find the project's test, lint and typecheck commands (`CLAUDE.md`, package manifest, Makefile). You will run them after every merge and hand them to the workers.

## 2. Schedule — as software architect

Read every queued ticket in full. For each ticket note:

- **Explicit dependencies:** the Refs section, phrases like "depends on", "nach Ticket", "baut auf", "setzt voraus", and tickets that extend or use something another queued ticket introduces (a "foundation" ticket followed by per-screen tickets is the classic case).
- **Area:** the modules, directories, components, data models and config files the ticket will touch — from the ticket text plus a quick look into the code where the text is vague.
- **Shared hotspots:** i18n catalogues, route or layout registries, schema and migration files, central stores, package manifests. Several tickets adding to the same hotspot is fine if the edits are additive; two tickets reshaping the same hotspot are not.

Then group the tickets into **lanes**:

- Two tickets belong to the same lane when one depends on the other, when they touch the same files, modules or data model, or when both reshape the same shared hotspot. Inside a lane the tickets run sequentially, in dependency order, claim order as tie-breaker.
- Tickets that touch different areas go into different lanes. Lanes run in parallel.
- Dependencies across lanes are not allowed: merge the two lanes into one instead.
- When in doubt whether two tickets conflict, put them in the same lane. A serial lane costs time; a conflicting merge costs correctness.
- Name each lane with a short slug of its theme (`filter-pills`, `ai-training`, …). Branches will be `svan/<lane>`.

Present the schedule to the user as a table: lane, tickets in order, why they are grouped, and which batch they run in given the parallel limit. This is informational — do not wait for an answer. With `--dry-run`, stop here.

## 3. Start a lane

Do this for every lane of the first batch, then launch all their workers in a single message so they run concurrently. Later lanes start the same way as earlier ones finish.

1. **Claim** all tickets of the lane: `scripts/claim_task.py <file> …` from the main directory moves them to `.tasks/doing/`. If `.tasks` is tracked, commit the claim on the current branch (`git add .tasks && git commit -m "svan-monkey-family: claim <numbers>"`) so the worktree sees the tickets in `doing`.
2. **Worktree:** `git worktree add .worktrees/<lane> -b svan/<lane>` from the current HEAD, so later lanes include the merged results of earlier ones. Make sure `.worktrees/` is ignored (`.gitignore` or `.git/info/exclude`). If the project needs an install step for a fresh checkout (`node_modules`, virtualenv, …), run it in the worktree before starting the worker.
3. **Worker:** read `WORKER.md`, fill in the placeholders and spawn a general-purpose agent with the full brief as its prompt. Placeholders: `WORKTREE` (absolute path), `BRANCH`, `TICKETS` (ordered list of ticket paths — inside the worktree under `.tasks/doing/` when `.tasks` is tracked, otherwise the absolute paths in the main checkout), `TICKET_LOCATION` (one sentence saying which of the two it is), `CHECKS` (the commands from step 1), `NOTES` (anything a worker must know: install steps, hotspots other lanes touch, pre-existing test failures). Never shorten the brief — it is all the worker gets.

## 4. Supervise and merge

Workers run in the background; you get notified when one finishes. Do not poll, do not predict results, and never write a worker's report yourself. When a worker finishes:

1. Read its report. For every ticket it reports as done, check that the ticket file is in `done` on the lane branch and the commits exist (`git log main..svan/<lane> --oneline`).
2. **Merge** in the main checkout: `git merge svan/<lane>`. If there are conflicts and they are mechanical (both sides appended imports, keys, routes, list entries), resolve them yourself as the architect, run the checks, commit. If a conflict is not mechanical, `git merge --abort`, keep the branch and worktree, and report the lane as unmerged with the conflicting files.
3. **Keep main green:** run the test / lint / typecheck commands after every merge. A failure that was green on the branch is a merge interaction: fix it if it is small and obvious, otherwise revert the merge (`git revert -m 1`) and report the lane as unmerged.
4. **Clean up** after a successful merge: `git worktree remove .worktrees/<lane>` and `git branch -d svan/<lane>`.
5. **Blocked or skipped tickets** stay in `.tasks/doing/` with the worker's notes; they are merged along with the rest. Do not retry them.
6. **Start the next queued lane** (step 3) from the updated HEAD.

A worker that fails without a report (crash, timeout) is handled like an unmerged lane: keep its branch and worktree, move its unclaimed tickets back from `doing` to `todo` with `git mv` (only the ones that have no commits on the branch), and report it.

Continue until every lane is merged or reported. Do not push.

## 5. Report

Final report in the language the tickets are written in (usually German), as a recap, not a log:

1. **Per ticket** one line: number, title, result (done / blocked / skipped / unmerged), lane.
2. **Decisions made on the user's behalf** that they will most likely want to review — the workers' least certain ones, with a pointer to the `Decisions & Assumptions` section of each ticket.
3. **Risks and manual test checklist**, aggregated across tickets.
4. **Follow-ups** the workers suggested, as candidates for new tickets.
5. **State of the repository:** merged branches, unmerged branches and their worktrees, what remains in `.tasks/doing/`, the test status of `main`, and that nothing was pushed.
