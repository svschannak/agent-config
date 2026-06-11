---
description: Processes next task from .tasks/todo without asking any questions
disable-model-invocation: true
---

This is the no-questions-asked variant of svan-next. Do NOT ask the user any questions and do NOT wait for confirmation — just implement the task end to end based solely on the task file.

Run `scripts/oldest_task.py` (resolve the path relative to this skill's directory) from the project's main directory. It claims the oldest markdown file in .tasks/todo (sorted by the datetime the file was added to the directory), moves it to .tasks/doing/, and prints the new path there. If the script reports the queue is empty (non-zero exit), tell the user there are no tasks and stop. Otherwise take the task description from the printed file, derive a plan yourself, and add the plan to the markdown file with tasks to complete, then start implementing immediately.

Mark the tasks after completing them and add the history while solving the task. After finishing the task move the task to .tasks/done/ and add the total time and used tokens to the yaml header of the markdown file. Add history and plan to the end of the file.

Also add a section for risks and what to test for. Inform the user about the risks of this ticket, what could go wrong and what should be tested manually.
