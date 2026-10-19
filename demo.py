#!/usr/bin/env python3
"""demo.py - one request, end to end: planner (Claude API) -> validator -> gate hook -> write -> trace.

    python demo.py            # no API key needed: the model's answers were recorded on a live run
    python demo.py --live     # call the API for any answer not recorded yet (needs ANTHROPIC_API_KEY)

What you will see, on a fictitious task board:
  1. The model tries to write straight away. The PreToolUse hook blocks it: no validated batch.
  2. Planner, round 1, sees only the day the request names (how the original failure happened).
     The validator rejects the batch: a forgotten day, an overdue task, a lost task.
  3. Planner, round 2, gets the whole board and the validator's report. The batch closes; the gate opens.
  4. The human approves; the same hook now lets the exact tool calls through; a fake Todoist applies them.
  5. Every stage is written to runs/<run>/trace.jsonl and shown as a table.
Nothing here touches a real Todoist account.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAGS = tempfile.mkdtemp(prefix="gate-flags-")
os.environ["GATE_FLAGS_DIR"] = FLAGS                     # before importing the gate modules
sys.path.insert(0, str(ROOT / "src"))

from llm.client import LLM  # noqa: E402
from todoist_gate import check_batch, planner  # noqa: E402
from tracing.trace import Trace  # noqa: E402
from tracing.view import table  # noqa: E402

HOOK = ROOT / "src" / "todoist_gate" / "gate_hook.py"
MAX_ROUNDS = 3


def say(title: str, body: str = "") -> None:
    print(f"\n=== {title} " + "=" * max(0, 74 - len(title)))
    if body:
        print(body)


def hook(call: dict) -> tuple[int, str]:
    """Run the hook exactly as Claude Code does: tool call as JSON on stdin; exit 2 = blocked."""
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(call), capture_output=True, text=True,
                       env=dict(os.environ, GATE_FLAGS_DIR=FLAGS))
    return p.returncode, p.stderr.strip()


def show_proposal(p: dict) -> str:
    lines = [f'Planner: "{p["summary"]}"']
    for d in sorted(p["days"], key=lambda d: d["date"]):
        lines.append(f"  {d['date']}")
        lines += [f"    {it['start']} {it['duration_min']:>3} min  {it['content']}" for it in d["items"]]
    for r in p["reschedule_overdue"]:
        lines.append(f"  overdue -> {r['date']}: {r['content']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    board = json.loads((ROOT / "examples" / "demo_board.json").read_text(encoding="utf-8"))
    llm = LLM(mode="auto" if "--live" in argv else "demo", max_calls=8)
    tr = Trace("demo", llm)

    say("Request", f'"{board["request"]}"\n(fictitious board: {board["today"]}, now {board["now"]}; '
                   f'model {llm.summary()["model"]}, mode {llm.mode})')

    with tr.step("hook: write before any batch") as s:
        first_try = {"tool_name": "mcp__todoist__reschedule-tasks",
                     "tool_input": {"tasks": [{"id": "t2", "dueString": "Mar 12 at 09:00"}]}}
        code, msg = hook(first_try)
        s["status"], s["detail"] = ("blocked", msg[:120]) if code == 2 else ("ok", "passed")
    say("1. The model tries to reschedule right away", f"hook exit {code}: {msg}")

    feedback, scope, closed = "", "day", None
    for rnd in range(1, MAX_ROUNDS + 1):
        with tr.step("planner (Claude API)", round=rnd) as s:
            proposal = planner.propose(llm, board, scope, feedback)
            s["detail"] = f"scope={scope}; {len(proposal['days'])} day(s)"
        say(f"{rnd + 1}. Planner, round {rnd} (sees {'only the requested day' if scope == 'day' else 'the whole board'})",
            show_proposal(proposal))
        with tr.step("validator (check_batch)", round=rnd) as s:
            res, text = planner.validate(board, proposal)
            n = sum(len(d["errors"]) for d in res["days"]) + len(res["blockers"]) + len(res["decisions"])
            s["status"], s["detail"] = ("ok", "batch closed") if res["ok"] else ("blocked", f"{n} problem(s)")
        print("\nValidator:\n" + text)
        if res["ok"]:
            closed = proposal
            break
        feedback, scope = text, "full"
    if closed is None:
        say("Result", f"BATCH OPEN after {MAX_ROUNDS} rounds: nothing is written. The human decides.")
        tr.close(outcome="open")
        return 1

    check_batch.FLAGS = FLAGS                            # the run's own flag folder, never the repo's
    check_batch.open_gate()
    calls = planner.writes(board, closed)
    with tr.step("human approval") as s:
        say("Approval", "Tool calls to send:\n" + planner.dumps(calls))
        if sys.stdin.isatty() and "--yes" not in argv:
            ok = input("\nApprove these writes? [y/N] ").strip().lower() == "y"
        else:
            ok = True
            print("\n(non-interactive run: approval simulated)")
        s["status"], s["detail"] = ("ok", "approved") if ok else ("blocked", "declined by the human")
    if not ok:
        tr.close(outcome="declined")
        return 1

    with tr.step("hook: write with a closed batch") as s:
        results = [hook(c) for c in calls]
        s["detail"] = ", ".join(f"{c['tool_name'].split('__')[-1]}: exit {r[0]}" for c, r in zip(calls, results))
        s["status"] = "ok" if all(r[0] == 0 for r in results) else "blocked"
    say("The same hook, now with the batch closed", s["detail"])
    if s["status"] != "ok":
        tr.close(outcome="blocked")
        return 1

    with tr.step("write (fake Todoist)") as s:
        n = sum(len(c["tool_input"]["tasks"]) for c, r in zip(calls, results) if r[0] == 0)
        s["detail"] = f"{n} task(s) written"
    print(f"{n} task(s) written to the fake board.")

    total = tr.close(outcome="written")
    say("Trace", table([json.loads(l) for l in tr.path.read_text(encoding="utf-8").splitlines()]))
    print(f"\n{total['api_calls']} API call(s) now (US$ {total['cost_usd']:.5f}); {total['recorded_answers']} recorded "
          f"answer(s) replayed (they cost US$ {total['recorded_cost_usd']:.5f} when recorded).\n"
          f"Trace: runs/{tr.run_id}/trace.jsonl - HTML view: python src/tracing/view.py --last --html trace.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
