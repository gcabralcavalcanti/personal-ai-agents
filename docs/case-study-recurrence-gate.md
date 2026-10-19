# Case study: the date change that killed recurring tasks

How a written rule became a hook, and why. Real error class from the Secretary agent's error taxonomy;
the task names below are fictitious.

## What went wrong
The task manager has two ways to change a date. `reschedule-tasks` moves one occurrence and keeps the
recurrence. `update-tasks` with a new `dueString` **replaces the recurrence rule** with the new date: a task
that repeated every Monday becomes a single task on Thursday, and nothing in the reply says so.

For a model both calls look like "change the date", and the wrong one fails silently: the tool answers
"updated", the agent reports "done", and the series is gone. Nothing shows it until the next occurrence
fails to appear. That is the worst kind of error for an agent: cheap to make, invisible, and found late.

## Why a rule in the prompt was not enough
The first fix was a line in the skill and in the error taxonomy (rule R2): *dates change through
reschedule-tasks, never update-tasks*. A rule in a long prompt is a request, not a guarantee: it competes with
every other instruction and depends on the model remembering it at the moment of the call. For an error that is
silent and expensive, "usually remembered" is not good enough. Instructions are context, not enforcement.

## The fix: a deterministic gate
When the agents moved to Claude Code (8 Oct 2026), R2 became a **PreToolUse hook**
([`gate_hook.py`](../src/todoist_gate/gate_hook.py)). The harness runs it before every Todoist write, with the
tool call as JSON on stdin:

```
update-tasks with a dueString  ->  exit 2, call blocked, and the model reads:
"BLOCKED (R2): change dates with reschedule-tasks, never update-tasks with dueString
 (it rewrites the rule and kills the recurrence). If the human approved a schedule change,
 run python src/todoist_gate/release.py I7, retry, then release.py --close."
```

Three design choices:
1. **Block, then explain.** The message tells the model the right tool, so it fixes the call by itself, without
   asking the human.
2. **A legitimate exception has a door, not a bypass.** Changing a recurrence on purpose (a new weekly time) is
   sometimes the goal. The human approves it in chat; `release.py I7` creates a flag; the hook lets
   `update-tasks` through; `--close` removes the flag.
3. **The door closes by itself.** A flag older than 15 minutes is deleted on the next check and reported, so a
   crashed session cannot leave it open.

The same hook carries the other rules that must never depend on the model's memory: no timed task is created
or moved unless the whole multi-day batch passed the validator in the last 15 minutes, and nothing is deleted
or un-completed without an explicit request.

## How it is tested
[`tests/test_gate_hook.py`](../tests/test_gate_hook.py) runs the hook exactly as the harness does (JSON on
stdin, exit code), with flags in a temporary folder:

| Case | Expected |
|---|---|
| `update-tasks` with `dueString` | blocked (exit 2), message names reschedule-tasks |
| same, with a fresh I7 flag | passes |
| same, with an I7 flag 16 minutes old | blocked, the message says the flag expired |
| `update-tasks` without a date | passes (renaming is fine) |
| garbage on stdin | passes: the hook never blocks by accident |

In production the rule also keeps its row in the error taxonomy, next to the error classes that became checks.

## What it cost and what it bought
About 140 lines of Python (hook + release) and 13 tests. In exchange the rule holds whatever the prompt
says and whatever the model version. The general lesson, applied across the system since:
**if a mistake is expensive and checkable, check it in code; keep the prompt for what only judgment can do.**
