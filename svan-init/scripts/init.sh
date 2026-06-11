#!/usr/bin/env bash
#
# svan-init: create the .tasks workflow structure in the current project.
# Idempotent — safe to re-run. Existing folders are left untouched and
# FORMAT.md is only written when it does not already exist.

set -euo pipefail

TASKS_DIR=".tasks"

for sub in backlog todo doing done; do
  mkdir -p "$TASKS_DIR/$sub"
  # .gitkeep makes git track the folder even while it holds no tasks.
  touch "$TASKS_DIR/$sub/.gitkeep"
done

FORMAT_FILE="$TASKS_DIR/FORMAT.md"

if [ -f "$FORMAT_FILE" ]; then
  echo "Kept existing $FORMAT_FILE"
else
  cat > "$FORMAT_FILE" <<'EOF'
# TITLE

## Problem

## Auswirkung

## Scope / Acceptance Criteria

## Out of Scope

## Refs
EOF
  echo "Created $FORMAT_FILE"
fi

echo "svan-init complete: $TASKS_DIR/{backlog,todo,doing,done}"
