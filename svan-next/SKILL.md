---
description: Processes next task from .tasks/todo
disable-model-invocation: true
---

Run `scripts/oldest_task.py` (resolve the path relative to this skill's directory) from the project's main directory. It claims the oldest markdown file in .tasks/todo (sorted by the datetime the file was added to the directory), moves it to .tasks/doing/, and prints the new path there. If the script reports the queue is empty (non-zero exit), tell the user there are no tasks and stop. Otherwise take the task description from the printed file and draft an initial plan for the task.

Before writing the plan down or starting any implementation, interrogate the task as thoroughly as possible. Ask the user as many questions as you can, and refine the plan after every round of answers. Run three distinct survey rounds, each from a different perspective, and ask the questions for each round before moving to the next:

A) **Product manager (heavily user focused):** Question the user value, the problem being solved, the target users, success metrics, edge cases, scope, and what is explicitly out of scope.
B) **UI/UX designer (clean, consistent interface):** Question the user flows, states (loading/empty/error), accessibility, and how the change stays consistent with existing patterns and components so the interface stays clean.
C) **Software architect (fits the project structure):** Question how the implementation fits the existing architecture, modules, data flow, and conventions; what can be reused vs. added; dependencies; performance; and migration/backward-compatibility concerns.

Keep asking follow-up questions until you have no meaningful open questions left, refining the plan with each answer. Always present the final, refined plan to the user and get an explicit confirmation before starting any implementation — never begin implementing without that confirmation. Add the plan to the markdown file with tasks to complete. Mark the tasks after completing the tasks and add the history while solving the task. After finishing the task move the task to .tasks/done/ and add the total time and used tokens to the yaml header of the markdown file. Add history and plan to the end of the file.

Also add a section for risks and what to test for. Inform the user about the risks of this ticket, what could go wrong and what should be tested manually.

Check if /clear was used to reset the session before starting the ticket. If the session is not fresh, ask the user if the session should be cleared.
