"""One request on a fictitious task board: planner (Claude API) -> validator -> approval -> gate hook -> write.

Returns everything that happened, for the terminal and for the HTML page. Nothing touches a real Todoist account:
the hook runs exactly as Claude Code runs it (tool call as JSON on stdin) and the writes go to a fake board.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from personal_ai_agents.llm.client import LLM
from personal_ai_agents.todoist_gate import check_batch, planner
from personal_ai_agents.tracing.trace import Trace

HOOK = Path(__file__).with_name("gate_hook.py")
MAX_ROUNDS = 3


def hook(call: dict, flags: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(call),
        capture_output=True,
        text=True,
        env=dict(os.environ, GATE_FLAGS_DIR=flags),
    )
    return p.returncode, p.stderr.strip()


def show_proposal(p: dict) -> str:
    lines = [f'Planner: "{p["summary"]}"']
    for d in sorted(p["days"], key=lambda d: d["date"]):
        lines.append(f"  {d['date']}")
        lines += [f"    {it['start']} {it['duration_min']:>3} min  {it['content']}" for it in d["items"]]
    for r in p["reschedule_overdue"]:
        lines.append(f"  overdue -> {r['date']}: {r['content']}")
    return "\n".join(lines)


def run(board: dict, llm: LLM, approve: Callable[[], bool], say: Callable[[str, str], None]) -> dict:
    flags = tempfile.mkdtemp(prefix="gate-flags-")
    tr = Trace("secretary", llm)
    out = {"board": board, "rounds": [], "calls": [], "approved": None, "hook_results": [], "written": 0}
    say("Request", f'"{board["request"]}"\n(fictitious board: {board["today"]}, now {board["now"]})')

    with tr.step("hook: write before any batch") as s:
        first = {
            "tool_name": "mcp__todoist__reschedule-tasks",
            "tool_input": {"tasks": [{"id": "t2", "dueString": "Mar 12 at 09:00"}]},
        }
        code, msg = hook(first, flags)
        s["status"], s["detail"] = ("blocked", msg[:120]) if code == 2 else ("ok", "passed")
    out["first_try"] = {"call": first, "exit": code, "message": msg}
    say("1. The model tries to reschedule right away", f"hook exit {code}: {msg}")

    feedback, scope, closed = "", "day", None
    for rnd in range(1, MAX_ROUNDS + 1):
        with tr.step("planner (Claude API)", round=rnd) as s:
            proposal = planner.propose(llm, board, scope, feedback)
            s["detail"] = f"scope={scope}; {len(proposal['days'])} day(s)"
        seen = "only the requested day" if scope == "day" else "the whole board"
        say(f"{rnd + 1}. Planner, round {rnd} (sees {seen})", show_proposal(proposal))
        with tr.step("validator (check_batch)", round=rnd) as s:
            res, text = planner.validate(board, proposal)
            n = sum(len(d["errors"]) for d in res["days"]) + len(res["blockers"]) + len(res["decisions"])
            s["status"], s["detail"] = ("ok", "batch closed") if res["ok"] else ("blocked", f"{n} problem(s)")
        say("Validator", text)
        out["rounds"].append({"round": rnd, "scope": scope, "proposal": proposal, "ok": res["ok"], "report": text})
        if res["ok"]:
            closed = proposal
            break
        feedback, scope = text, "full"

    if closed is not None:
        check_batch.FLAGS = flags
        check_batch.open_gate()
        out["calls"] = planner.writes(board, closed)
        with tr.step("human approval") as s:
            say("Approval", "Tool calls to send:\n" + planner.dumps(out["calls"]))
            out["approved"] = approve()
            s["status"], s["detail"] = ("ok", "approved") if out["approved"] else ("blocked", "not approved")
        if out["approved"]:
            with tr.step("hook: write with a closed batch") as s:
                out["hook_results"] = [hook(c, flags) for c in out["calls"]]
                pairs = zip(out["calls"], out["hook_results"], strict=True)
                s["detail"] = ", ".join(f"{c['tool_name'].split('__')[-1]}: exit {r[0]}" for c, r in pairs)
                s["status"] = "ok" if all(r[0] == 0 for r in out["hook_results"]) else "blocked"
            say("The same hook, now with the batch closed", s["detail"])
            with tr.step("write (fake Todoist)") as s:
                ok_calls = [c for c, r in zip(out["calls"], out["hook_results"], strict=True) if r[0] == 0]
                out["written"] = sum(len(c["tool_input"]["tasks"]) for c in ok_calls)
                s["detail"] = f"{out['written']} task(s) written"
        else:
            say("Not approved", "nothing written. Run `python demo.py secretary --yes` to approve and see the write.")
    else:
        say("Result", f"BATCH OPEN after {MAX_ROUNDS} rounds: nothing is written. The human decides.")

    out["closed"] = closed
    out["total"] = tr.close(outcome="written" if out["written"] else "not written")
    out["trace"] = [json.loads(line) for line in tr.path.read_text(encoding="utf-8").splitlines()]
    out["trace_path"] = str(tr.path)
    return out
