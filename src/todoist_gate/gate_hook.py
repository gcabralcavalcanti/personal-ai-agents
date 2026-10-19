#!/usr/bin/env python3
"""gate_hook.py - Claude Code PreToolUse hook that guards writes to Todoist.

Claude Code runs this script before every matching MCP tool call (see .claude/settings.example.json),
passing the tool call as JSON on stdin. Exit code 2 BLOCKS the call and the stderr text is shown to the
model, so it knows why and what to do next. Exit 0 lets the call through.

Rules enforced (deterministic - they do not depend on the model remembering a prompt):
  R2   update-tasks carrying a dueString is blocked: changing a date through "update" rewrites the
       recurrence rule and silently kills recurring tasks. Dates change through reschedule-tasks.
  GATE add-tasks / reschedule-tasks with a time of day pass only if check_batch.py closed the batch
       in the last 15 minutes (it writes the GATE-OK flag). Tasks without a time do not occupy the
       calendar and are exempt.
  R36  delete-object / uncomplete-tasks are blocked unless the human explicitly asked for it.

Unlocking: after the human approves in chat, `python src/todoist_gate/release.py I7|DELETE` creates a
flag file; `release.py --close` removes it. Flags expire after 15 minutes: a crashed session cannot
leave the door open.

Flag directory: $GATE_FLAGS_DIR, or <repo>/.flags by default (kept out of git).
"""
import json
import os
import re
import sys
import time

VALIDITY_S = 15 * 60
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLAGS = os.environ.get("GATE_FLAGS_DIR") or os.path.join(REPO, ".flags")
RELEASE = "python src/todoist_gate/release.py"
expired = []


def flag(name):
    """True if the flag exists and is younger than 15 min. An expired flag is deleted and reported."""
    p = os.path.join(FLAGS, name)
    if not os.path.exists(p):
        return False
    if time.time() - os.path.getmtime(p) <= VALIDITY_S:
        return True
    try:
        os.remove(p)
    except OSError:
        pass
    expired.append(name)
    return False


def note():
    return (f" (Flag {expired[0]} was older than 15 minutes and was deleted: recreate it only if the human "
            "approved again.)" if expired else "")


def has_due(obj):
    if isinstance(obj, dict):
        return "dueString" in obj or any(has_due(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_due(v) for v in obj)
    return False


TIME_OF_DAY = re.compile(r"\d{1,2}(:\d{2}|h\d{0,2}\b|\s?(am|pm)\b)", re.I)


def without_time(inp):
    """add-tasks where no task has a time of day: it does not occupy the calendar, so no clash is possible."""
    tasks = inp.get("tasks") if isinstance(inp, dict) else None
    return bool(tasks) and all(not TIME_OF_DAY.search(str(t.get("dueString") or ""))
                               for t in tasks if isinstance(t, dict))


def decide(name, inp):
    """Return (exit_code, message)."""
    if re.search(r"update-tasks", name) and has_due(inp) and not flag("I7-OK"):
        return 2, ("BLOCKED (R2): change dates with reschedule-tasks, never update-tasks with dueString "
                   "(it rewrites the rule and kills the recurrence). If the human approved a schedule change, "
                   f"run {RELEASE} I7, retry, then {RELEASE} --close." + note())
    if re.search(r"add-tasks", name) and without_time(inp):
        pass  # untimed tasks skip the batch check; reschedule-tasks is still gated
    elif re.search(r"add-tasks|reschedule-tasks", name) and not flag("GATE-OK"):
        return 2, ("BLOCKED (gate): create or reschedule only after the batch passed the checker in the last "
                   "15 min. Run python src/todoist_gate/check_batch.py <batch.json>; a CLOSED batch opens "
                   "the gate for 15 min." + note())
    if re.search(r"delete-object|uncomplete-tasks", name) and not flag("DELETE-OK"):
        return 2, ("BLOCKED (R36): delete-object and uncomplete-tasks only on a direct, specific request from "
                   f"the human. If asked, run {RELEASE} DELETE, retry, then {RELEASE} --close." + note())
    return 0, ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # not a hook payload: never block by accident
    code, msg = decide(str(data.get("tool_name", "")), data.get("tool_input") or {})
    if code:
        sys.stderr.write(msg + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
