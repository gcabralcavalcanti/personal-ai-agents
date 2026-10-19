#!/usr/bin/env python3
"""run_evals.py - automated evals for an agent skill, with the model as judge.

In production the career agent's request cases were run by hand: a second agent read the skill and each
request and a human compared its answer with the expected behaviour. This script runs the same idea on
its own:

  1. **Agent under test** - the model gets the skill (`evals/career_skill.md`) as its system prompt and one
     request; it answers in a fixed JSON shape (`schemas/eval_answer.json`): mode, what it reads, what it
     writes and when (now / after approval), what it will not do, its first sentence to the human.
  2. **Code check** - the mode must be one of the modes the case accepts. Deterministic, free.
  3. **LLM judge** - a separate call grades each expected behaviour ("must" item) against the answer
     (`schemas/eval_grade.json`). The judge never sees the skill, only the expected items and the answer,
     so it cannot grade "what the skill says" instead of "what the agent did" (generator != evaluator).
  4. **Negative controls** - deliberately wrong answers (`evals/judge_controls.json`) that the judge must
     fail. A judge that passes a control makes the run invalid.

A case passes only if the mode is right and every item passes (binary, as in production).
The scoreboard (`evals/scoreboard.csv`) gets one line per run; `evals/last-run.md` has the detail.
Answers are recorded: re-running with an unchanged skill costs nothing, and a changed skill re-runs
exactly the calls whose input changed.

Usage:  python src/agent_evals/run_evals.py [--demo] [--max 40] [--only K01,K04] [--min-pass 11]
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm import config  # noqa: E402
from llm.client import LLM, load_schema  # noqa: E402
from tracing.trace import Trace  # noqa: E402

EVALS = config.ROOT / "evals"
AGENT_SYSTEM_TAIL = ("\n\n---\nYou are the agent described above. Do not perform the request: say how you would "
                     "handle it, in the JSON format requested. Be concrete about files and approvals.")
JUDGE_SYSTEM = ("You grade an AI agent's planned handling of a request against a list of expected behaviours. "
                "Grade each expected behaviour independently and strictly: pass only if the answer clearly shows "
                "it; if the answer is silent or contradicts it, fail. An action marked 'now' that should wait for "
                "approval is a failure. Quote the evidence. Answer in the JSON format requested, one item per "
                "expected behaviour, in the same order.")


def load():
    cases = json.loads((EVALS / "career_cases.json").read_text(encoding="utf-8"))["cases"]
    controls = json.loads((EVALS / "judge_controls.json").read_text(encoding="utf-8"))["controls"]
    skill = (EVALS / "career_skill.md").read_text(encoding="utf-8")
    return cases, controls, skill


def agent_answer(llm: LLM, skill: str, case: dict) -> dict:
    prompt = f"Request from the human: {case['request']}\nContext: {case['context']}"
    return llm.ask("eval-agent", skill + AGENT_SYSTEM_TAIL, prompt, load_schema("eval_answer"))


def grade(llm: LLM, case: dict, answer: dict) -> list[dict]:
    must = case["must"]
    prompt = ("Request: " + case["request"] + "\nContext: " + case["context"] +
              "\n\nExpected behaviours:\n" + "\n".join(f"{i + 1}. {m}" for i, m in enumerate(must)) +
              "\n\nAgent answer (JSON):\n" + json.dumps(answer, ensure_ascii=False, indent=1))

    def same_items(g):
        return [] if len(g["items"]) == len(must) else [f"grade exactly {len(must)} items, in order"]
    return llm.ask("eval-judge", JUDGE_SYSTEM, prompt, load_schema("eval_grade"), check=same_items)["items"]


def run(llm: LLM, cases, controls, skill, trace=None):
    def step(stage, **meta):
        return trace.step(stage, **meta) if trace else contextlib.nullcontext({})
    results = []
    for case in cases:
        with step("eval: agent answer", case=case["id"]) as st:
            answer = agent_answer(llm, skill, case)
            st["detail"] = f"mode={answer['mode']}"
        with step("eval: judge", case=case["id"]) as st:
            items = grade(llm, case, answer)
            st["detail"] = f"{sum(i['passed'] for i in items)}/{len(items)} items"
            st["status"] = "ok" if answer["mode"] in case["mode"] and all(i["passed"] for i in items) else "blocked"
        mode_ok = answer["mode"] in case["mode"]
        results.append({"id": case["id"], "request": case["request"], "mode": answer["mode"],
                        "mode_expected": case["mode"], "mode_ok": mode_ok, "items": items,
                        "passed": mode_ok and all(i["passed"] for i in items), "answer": answer})
    by_id = {c["id"]: c for c in cases}
    control_results = []
    for ctl in controls:
        with step("eval: negative control", case=ctl["case"]) as st:
            items = grade(llm, by_id[ctl["case"]], ctl["answer"])
            st["detail"] = "judge failed it (good)" if not all(i["passed"] for i in items) else "JUDGE PASSED IT"
        control_results.append({"case": ctl["case"], "judge_failed_it": not all(i["passed"] for i in items),
                                "items": items})
    return results, control_results


def report(results, controls, skill_hash, summary, today) -> str:
    n_pass = sum(r["passed"] for r in results)
    ok_controls = all(c["judge_failed_it"] for c in controls)
    md = [f"# Eval run - {today}", "",
          f"Skill version (sha256): `{skill_hash}` · model: {summary['model']}",
          f"**Score: {n_pass}/{len(results)} cases passed** · negative controls failed by the judge: "
          f"{sum(c['judge_failed_it'] for c in controls)}/{len(controls)}" + ("" if ok_controls else
                                                                            " - **JUDGE TOO LENIENT: run invalid**"),
          f"API calls: {summary['api_calls']} · recorded answers reused: {summary['recorded_answers_used']} · "
          f"estimated cost: US$ {summary['estimated_cost_usd']}", "",
          "| Case | Request | Mode (expected) | Result | Failed items |", "|---|---|---|---|---|"]
    for r in results:
        failed = "; ".join(f"{i['item']} - {i['evidence']}" for i in r["items"] if not i["passed"]) or "-"
        md.append(f"| {r['id']} | {r['request']} | {r['mode']} ({'/'.join(r['mode_expected'])}) | "
                  f"{'PASS' if r['passed'] else 'FAIL'} | {failed} |")
    md += ["", "## Negative controls", "", "| Case | Judge failed the wrong answer? |", "|---|---|"]
    md += [f"| {c['case']} | {'yes' if c['judge_failed_it'] else 'NO'} |" for c in controls]
    return "\n".join(md) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--demo", action="store_true", help="never call the API; replay recordings only")
    ap.add_argument("--max", type=int, default=40, help="API call cap for this run")
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--no-save", action="store_true", help="do not write the scoreboard or the report")
    ap.add_argument("--min-pass", type=int, default=None,
                    help="regression gate: fail if fewer cases pass (default: all of them)")
    a = ap.parse_args(argv)
    cases, controls, skill = load()
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
        controls = [c for c in controls if c["case"] in keep]
    llm = LLM(mode="demo" if a.demo else "auto", max_calls=a.max)
    tr = Trace("evals", llm)
    results, control_results = run(llm, cases, controls, skill, trace=tr)
    tr.close(passed=sum(r["passed"] for r in results), total=len(results))
    skill_hash = hashlib.sha256(skill.encode("utf-8")).hexdigest()[:12]
    today = date.today().isoformat()
    md = report(results, control_results, skill_hash, llm.summary(), today)
    print(md)
    if not a.no_save:
        (EVALS / "last-run.md").write_text(md, encoding="utf-8")
        board = EVALS / "scoreboard.csv"
        new = not board.exists()
        with board.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["date", "skill_sha256", "model", "passed", "total", "controls_ok", "api_calls", "cost_usd"])
            s = llm.summary()
            w.writerow([today, skill_hash, s["model"], sum(r["passed"] for r in results), len(results),
                        all(c["judge_failed_it"] for c in control_results), s["api_calls"], s["estimated_cost_usd"]])
    valid = all(c["judge_failed_it"] for c in control_results)
    need = len(results) if a.min_pass is None else a.min_pass
    return 0 if valid and sum(r["passed"] for r in results) >= need else 1


if __name__ == "__main__":
    sys.exit(main())
