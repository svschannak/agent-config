---
description: Processes the next task from .tasks/todo autonomously — same procedure as svan-next (PM / UI-UX / architect rounds, plan, implement, finish) but every question is asked and answered by the agent itself, never by the user
disable-model-invocation: true
---

This is the autonomous variant of svan-next. It runs the same procedure — claim, interrogate the ticket in three roles, plan, implement, verify, finish — but it never asks the user anything. Every question svan-next would put to the user, you ask yourself and answer yourself. Do not use AskUserQuestion, do not wait for confirmation, do not stop for a "fresh session" check. The only reasons to end early are an empty queue or a genuinely blocked ticket (see "Blocked" below).

## 1. Claim

Run `scripts/oldest_task.py` (resolve the path relative to this skill's directory) with `python3` from the project's main directory. It claims the oldest markdown file in `.tasks/todo` (sorted by the datetime the file was added to the directory), moves it to `.tasks/doing/` and prints the new path. If the script reports the queue is empty (non-zero exit), tell the user there are no tasks and stop. Note the start time.

## 2. Understand

Read the claimed ticket in full. Then read what the project says about itself before forming any opinion: `CLAUDE.md`, `.tasks/FORMAT.md`, the README / package manifest (for the test, lint and typecheck commands), and the done tickets the ticket references or that touch the same area (`grep -l` over `.tasks/done`). Explore the code the ticket touches — modules, components, data model, existing patterns — so that your decisions below are grounded in the actual codebase, not in assumptions.

Note the ticket's `complexity` (S / M / L) from the YAML header, if present. If the code turns out to be clearly harder or easier than that, record it as a decision under `## Decisions & Assumptions` (role: Arch) — it tells the user how well tickets are being sized.

## 3. Interrogate the ticket — three roles, against yourself

Run the three survey rounds of svan-next, but you are both interviewer and interviewee. For each role, list the questions that role would ask about this ticket, then answer every one of them from the ticket, the codebase, `CLAUDE.md` and the done tickets. Run the rounds in this order and finish one before starting the next:

A) **Product manager (heavily user focused):** user value, the problem being solved, target users, success criteria, edge cases, scope, and what is explicitly out of scope. Which acceptance criteria are ambiguous, and what is the most plausible reading?
B) **UI/UX designer (clean, consistent interface):** user flows, states (loading / empty / error / disabled), accessibility, wording and i18n, and how the change stays consistent with the existing components and patterns so the interface stays clean. Which existing component or screen is the closest precedent?
C) **Software architect (fits the project structure):** how the change fits the existing architecture, modules, data flow and conventions; what can be reused vs. must be added; dependencies; performance; migration / backward compatibility; how it will be tested.

**Decision rule.** Whenever a question stays open after consulting all sources, decide it yourself — and choose the option you would have presented to the user as "(Recommended)": the smallest change that satisfies every acceptance criterion, follows the project's existing patterns, and does not widen the scope. Prefer reuse over new abstractions, the project's conventions over your own taste, and reversible choices over irreversible ones. Do not invent requirements, and treat the ticket's "Out of Scope" section as binding.

Record every decision in the ticket under `## Decisions & Assumptions`, one bullet each: the question, the choice you made, one line of rationale, and the role that raised it (PM / UX / Arch). This section replaces the conversation svan-next would have had with the user. It is what the user reads afterwards to see what you decided on their behalf, so keep it complete and honest — including decisions you are not sure about, marked as such.

## 4. Plan

Append to the ticket, in this order:

- `## Decisions & Assumptions` (from step 3)
- `## Risks & What to Test` — what could go wrong, what must be tested manually, which existing behaviour could regress.
- `## Implementation Plan (YYYY-MM-DD)` with a short description and a `### Tasks` list of checkboxes, each small enough to be verified on its own.

Then start implementing immediately — there is no confirmation step.

## 5. Implement

Work through the tasks in order. Tick off each checkbox when it is done and keep a dated `## History` section at the end of the ticket with what you did, what you found and what you changed in the plan — in the same style as the existing done tickets. Stay inside the ticket's scope: if you discover something adjacent worth doing, write it under `## Follow-ups` as a suggestion for a new ticket instead of doing it.

After the implementation run the project's test, lint and typecheck commands. Fix failures you caused. Pre-existing failures are noted in the History, not fixed.

## 6. Finish

1. Update the YAML header of the ticket: `status: done`, `completed: YYYY-MM-DD`, `total_time` and `tokens_used` (approximate values are fine, e.g. `~35 min`, `~95k`). Add `## Outcome / Notes` with the result in two to five lines, including anything that was deliberately not done.
2. Move the ticket to `.tasks/done/`.
3. Commit on the current branch: stage only the files you touched plus the moved ticket file (never sweep in unrelated uncommitted changes). Message: `<ticket-number>: <title>` and a short body. End the message with the trailer `Svan-Ticket: <ticket-number>` in the final trailer block: after a blank line, directly above `Co-Authored-By:` and any other trailers, with no blank line between them (git only parses the last paragraph as trailers) — on every commit that belongs to a ticket, including blocked or partial work and later fixes; a commit serving several tickets gets `Svan-Ticket: 010, 011`. The svan viewer finds a ticket's code only through this trailer. Do not push.
4. Report to the user in the language the ticket is written in (usually German): what was implemented, the decisions you made on their behalf (point to the section in the ticket and name the ones you are least sure about), the risks and the manual test checklist, and the follow-ups. If the ticket's `complexity` and the model of this session do not match (S or M run on the most capable model, L run on a smaller one), say so in one line, so the user can switch with `/model` next time. Keep it a recap, not a log.

## Blocked

A ticket is blocked only if it cannot be implemented responsibly without the user: contradictory acceptance criteria that cannot be reconciled by the decision rule, missing credentials or external services, or references to code that does not exist. Guessing is not an option in these cases. Implement every part that is not blocked, set `status: blocked` in the YAML header, describe precisely what is missing under `## Blocked`, leave the ticket in `.tasks/doing/`, commit what you have, and report the blocker to the user. Do not block for mere uncertainty — that is what the decision rule is for.
