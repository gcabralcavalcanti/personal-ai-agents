#!/usr/bin/env python3
"""Run every agent and write its page to output/ (plus an index), then open the index.

    python demo.py                      # all agents on fictitious data; asks before the calendar writes
    python demo.py secretary            # one agent: secretary | habits | goals | career | study
    python demo.py --yes --no-open      # approve without asking, do not open a browser (scripts, CI)
    python demo.py --live               # call Claude for any answer not recorded yet (needs ANTHROPIC_API_KEY)

With your own data (see "Use it with your own data" in the README):
    python demo.py habits --input "Loop Habits Backup.db"        # or the CSV export .zip
    python demo.py goals --input <export> --goals my_goals.json
    python demo.py career --sources my_sources.csv --profile my_profile.json --live
    python demo.py secretary --board my_board.json --request "move the review to Thursday" --live
    python demo.py study --week my_week.json
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from personal_ai_agents import pages  # noqa: E402
from personal_ai_agents.career import job_delta, triage  # noqa: E402
from personal_ai_agents.career import page as career_page  # noqa: E402
from personal_ai_agents.goals import panel  # noqa: E402
from personal_ai_agents.habits import dashboard, loop  # noqa: E402
from personal_ai_agents.llm.client import LLM  # noqa: E402
from personal_ai_agents.study import page as study_page  # noqa: E402
from personal_ai_agents.study import plan as study_plan  # noqa: E402
from personal_ai_agents.todoist_gate import page as secretary_page  # noqa: E402
from personal_ai_agents.todoist_gate import run as secretary_run  # noqa: E402
from personal_ai_agents.tracing.view import table  # noqa: E402

DATA, OUT = ROOT / "data", ROOT / "output"
EXPORT_END = date(2026, 11, 15)  # last day in the fictitious habit-app export


def say(title: str, body: str = "") -> None:
    print(f"\n=== {title} " + "=" * max(0, 74 - len(title)))
    if body:
        print(body)


def quiet(title: str, body: str = "") -> None:
    pass


def approve_from(yes: bool):
    def approve() -> bool:
        """--yes approves; otherwise ask, and treat no keyboard (pipe, CI, script) as "not approved"."""
        if yes:
            print("\n(--yes: approved)")
            return True
        if not sys.stdin.isatty():
            print("\n(no interactive terminal: not approved)")
            return False
        try:
            return input("\nApprove these writes? [y/N] ").strip().lower() == "y"
        except EOFError:
            return False

    return approve


def llm_for(opts, max_calls: int) -> LLM:
    return LLM(mode="auto" if opts.live else "demo", max_calls=max_calls)


def secretary(opts, verbose: bool) -> str:
    board = json.loads(Path(opts.board or DATA / "demo_board.json").read_text(encoding="utf-8"))
    if opts.request:
        board["request"] = opts.request
    r = secretary_run.run(board, llm_for(opts, 8), approve_from(opts.yes), say if verbose else quiet)
    (OUT / "secretary.html").write_text(secretary_page.page(r), encoding="utf-8")
    if verbose:
        say("Trace", table(r["trace"]))
        t = r["total"]
        print(
            f"\n{t['api_calls']} API call(s) now (US$ {t['cost_usd']:.5f}); {t['recorded_answers']} recorded "
            f"answer(s) replayed (they cost US$ {t['recorded_cost_usd']:.5f} when recorded)."
        )
    if verbose or opts.yes:
        print(f"{r['written']} task(s) written" if r["written"] else "nothing written: not approved")
    return f"a bad batch blocked by the gate; the plan closed in round {len(r['rounds'])}, then waits for approval"


def habit_data(opts):
    if opts.input:
        export = Path(opts.input)
        habits, marks = loop.read_any(export)
        return export, habits, marks, loop.last_day(marks)
    export = DATA / "loop-habits-export.zip"
    if not export.exists():
        loop.write_fictitious_export(export, EXPORT_END)
    habits, marks = loop.read_export(export)
    return export, habits, marks, EXPORT_END


def habits(opts, verbose: bool) -> str:
    export, hab, marks, end = habit_data(opts)
    rows = dashboard.summary(hab, marks, end)
    dashboard.write_spreadsheet(OUT / "habits.xlsx", hab, marks, rows, end)
    shown = export.name if opts.input else f"data/{export.name}"
    (OUT / "habits.html").write_text(dashboard.page(rows, marks, end, shown, "output/habits.xlsx"), encoding="utf-8")
    green = sum(1 for r in rows if dashboard.light(r["r30"]) == "ok")
    return f"{len(rows)} habits from the app export; {green} on target over the last 30 days"


def goals(opts, verbose: bool) -> str:
    _, _, marks, end = habit_data(opts)
    g = json.loads(Path(opts.goals or DATA / "goals.json").read_text(encoding="utf-8"))
    results = panel.evaluate(g, marks, end)
    (OUT / "goals.html").write_text(panel.page(g, results, end), encoding="utf-8")
    behind = sum(1 for o in results for k in o["krs"] if k["status"] != "ok")
    return f"{len(results)} goals, {behind} key result(s) behind or off track"


def career(opts, verbose: bool) -> str:
    profile = json.loads(Path(opts.profile or DATA / "triage_profile.json").read_text(encoding="utf-8"))
    if opts.sources:  # your own list of public career pages, read live
        state_dir = OUT / "career-state"
        state_path = state_dir / "state.json"
        previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        today = date.today().isoformat()
        state, _ = job_delta.run(job_delta.read_sources(opts.sources), previous, today)
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        snap = {"date": today, "state": state}
    else:
        snap = json.loads((DATA / "job_board_snapshot.json").read_text(encoding="utf-8"))
        snap["state"].update(json.loads((DATA / "example_openings.json").read_text(encoding="utf-8"))["state"])
    llm = llm_for(opts, 25)
    store: dict = {}
    counts = triage.triage(snap["state"], store, profile, llm, snap["date"], llm.max_calls)
    page = career_page.page(store, counts, {"api_calls": llm.calls}, profile, snap["date"])
    (OUT / "career.html").write_text(page, encoding="utf-8")
    by = {d: sum(1 for r in store.values() if r.get("decision") == d) for d in ("apply", "monitor", "discard")}
    left = f", {counts['left_for_next_run']} waiting (run with --live)" if counts["left_for_next_run"] else ""
    return f"{counts['new']} openings: {by['apply']} apply, {by['monitor']} monitor, {by['discard']} discard{left}"


def study(opts, verbose: bool) -> str:
    week = json.loads(Path(opts.week or DATA / "study_week.json").read_text(encoding="utf-8"))
    r = study_plan.run(week, approve_from(opts.yes))
    (OUT / "study.html").write_text(study_page.page(r), encoding="utf-8")
    final = r["rounds"][-1]
    state = "passed the checker" if final["ok"] else "still open"
    orphans = len(r["audit"]["orphans"])
    return f"{orphans} deck(s) without a block; fitted plan with {len(final['blocks'])} block(s) {state}"


AGENTS = {"secretary": secretary, "habits": habits, "goals": goals, "career": career, "study": study}


def parse(argv: list[str]):
    ap = argparse.ArgumentParser(description="Run the agents' demos and write their pages to output/.")
    ap.add_argument("agents", nargs="*", help=f"which agents: {', '.join(AGENTS)} (default: all)")
    ap.add_argument("--yes", action="store_true", help="approve writes without asking")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--live", action="store_true", help="call Claude for answers not recorded yet")
    ap.add_argument("--input", help="your Loop Habits export (.zip) or backup (.db)")
    ap.add_argument("--goals", help="your goals file (format: data/goals.json)")
    ap.add_argument("--sources", help="your list of public career pages (format: data/sources.csv)")
    ap.add_argument("--profile", help="your candidate profile (format: data/triage_profile.json)")
    ap.add_argument("--board", help="your task board (format: data/demo_board.json, or todoist_export.py)")
    ap.add_argument("--request", help="the change you want on the board")
    ap.add_argument("--week", help="your flashcard forecast and week (format: data/study_week.json)")
    opts = ap.parse_args(argv)
    unknown = [a for a in opts.agents if a not in AGENTS]
    if unknown:
        ap.error(f"unknown agent(s) {unknown}; choose from {', '.join(AGENTS)}")
    return opts


def main(argv=None) -> int:
    opts = parse(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(exist_ok=True)
    chosen = opts.agents or list(AGENTS)
    status = {}
    for name in chosen:
        status[name] = AGENTS[name](opts, verbose=len(chosen) == 1)
        print(f"{name:<10} {status[name]}  ->  output/{name}.html")
    if len(chosen) == len(AGENTS):
        (OUT / "index.html").write_text(pages.index(status), encoding="utf-8")
    target = OUT / ("index.html" if len(chosen) > 1 else f"{chosen[0]}.html")
    print(f"\nOpen {target.relative_to(ROOT)}")
    if not opts.no_open:
        webbrowser.open(target.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
