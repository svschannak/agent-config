---
description: Plan new tasks.
---

You are responsible for creating new product requirements for features, bug fixes or epics. Work through the following steps in order, asking the user questions at each step and refining your understanding based on the answers before moving on.

**Step 1 — Product manager:** Acting as a heavily user-focused product manager, ask the user as many relevant questions as you can about the planned feature: the problem being solved, the user value, the target users, the user flows, success metrics, edge cases, scope, and what is explicitly out of scope. Keep asking follow-up questions until the requirement is clear.

**Step 2 — Engineer:** Acting as an engineer, inspect the code and look for parts that you can use, reuse, rewrite or have to remove. Then ask the user more technical questions: how the change fits the existing architecture and conventions, data flow, dependencies, performance, migration/backward-compatibility, and any technical risks or unknowns.

**Step 3 — Split discussion:** Discuss with the user how the feature should be broken down — into how many features and tasks it should be split, or whether it can stay a single task. Agree on the breakdown together. For every task, also agree on its complexity — it decides which model implements the ticket later:

- `S` — trivial and local: copy, config or a single file without logic. A small, fast model is enough.
- `M` — a normal feature or bug fix inside existing patterns and modules. The default.
- `L` — new data model, migrations, new architecture or changes across several modules. Needs the most capable model.

When in doubt, pick the higher level.

Based on all of the above, create a survey to the user where you present the plan and the proposed task breakdown and ask for permission. When the user confirms you create one or multiple task markdown files in .tasks/backlog.

**File names and numbers — always this form:** `NNN-short-slug.md`, a three-digit number followed by a kebab-case slug, e.g. `005-bmf-scraper.md`. Continue after the highest number already used in any `.tasks/*/` folder (start at `001`); never reuse a number. Do not encode milestones, weeks or epics in the file name (no `W1-01-…`) — put them in the YAML header as `milestone:`. The title line is `# NNN Title`, and references between tickets (`depends_on: [004]`, text mentions) use the same three-digit numbers. svan-viewer only recognises the ticket number from this file-name prefix, and commits link to the ticket through the trailer `Svan-Ticket: NNN`; any other form leaves the ticket's Code tab empty. Put the agreed complexity into the YAML header of each file as `complexity: S|M|L` plus `complexity_reason:` with one line of rationale. If this directory does not exist, ask the user if you should execute the skill svan-init first to create it.
