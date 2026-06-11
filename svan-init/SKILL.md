---
description: Setup for the svan workflow.
disable-model-invocation: true
effort: low
---

Run `scripts/init.sh` (resolve the path relative to this skill's directory) from the project's main directory.

The script is idempotent: it creates a `.tasks/` directory with the subdirectories `backlog`, `todo`, `doing`, and `done`, and writes `.tasks/FORMAT.md` only if it does not already exist. Existing folders and an existing `FORMAT.md` are left untouched, so there is nothing to confirm before running.

Report the script's output to the user.
