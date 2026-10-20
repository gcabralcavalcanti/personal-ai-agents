# Secretary (Todoist agent)

## Problem
A packed personal calendar with recurring blocks, fixed commitments and one-off tasks. Asking a model to
"move X to Thursday" worked on the day it looked at and broke the neighbouring days: overlaps, tasks left
in the past, recurring rules silently destroyed. The model "felt" done; the calendar was not.

## How it works
Planner -> validator -> writer, with the validator as a hard gate.
1. **Interpret** the request, even informal ("woke up late, push everything").
2. **Pull** the live tasks through the Todoist MCP connector. A post-call hook saves the raw response to a
   file, so the checker reads the real data instead of a retyped copy.
3. **Propose** a batch (JSON) covering every day it touches.
4. **Validate** with `check_batch.py`: per-day checks + cross-day checks. Exit 0 opens the gate for 15 min.
5. **Human approves** the proposal in chat.
6. **Write** through the MCP. The `PreToolUse` hook refuses the write if the gate is not open.

## Guardrails
| Rule | Enforced by |
|---|---|
| No timed create/reschedule without a closed batch in the last 15 min | `gate_hook.py` (hook, deterministic) |
| No date change via `update-tasks` (it kills recurrences) | `gate_hook.py` (R2) |
| No delete / un-complete without an explicit request | `gate_hook.py` (R36) + `release.py` flag |
| Approval flags expire after 15 min | hook deletes stale flags |
| Every past mistake becomes a check + a regression case | error taxonomy (production) |

Other agents that need to write tasks (career, librarian) go through the same gate.

## Tests
Production: 73 backtest cases (each reproduces a historical error class) plus 412 scripted checks in 10 more
suites, run by a single `verify_all` script before any change is committed (all 485 passing on 18 Oct 2026).
This repo: `tests/test_gate_hook.py` (runs the hook exactly as the harness does: JSON on stdin, exit code)
and `tests/test_check_batch.py` (golden cases on fictitious batches).

## Example (fictitious)
Request: "move the weekly report to Thursday". The first proposal (`data/batch_blocked.json`) fails:
```
OPEN 2026-03-11  - OVERLAP: "Deep work: thesis chapter 2" (09:00) x "Weekly report" (10:30)
GLOBAL BLOCKERS  - PAST_DIRTY: 1 overdue task(s) still on the board
                 - COVERAGE: touched day(s) not in the batch: 2026-03-13
                 - DEP_CROSSDAY: "Run regression" needs "Download dataset" first
BATCH OPEN - do not write, do not report done.
```
The corrected proposal (`data/batch_ok.json`) closes the batch and opens the gate.

## Run it end to end
`python demo.py` plays one request on a fictitious board: the hook blocks a write with no batch, the planner
(Claude API, recorded answers) proposes, the validator rejects round 1 and closes round 2, the human approves,
the hook lets the exact calls through, and every stage lands in a trace. The planner is
`personal_ai_agents/todoist_gate/planner.py`; in production that role is the Claude Code session itself.
Why the hook exists: [case study](case-study-recurrence-gate.md).

