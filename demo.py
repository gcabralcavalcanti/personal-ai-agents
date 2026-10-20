#!/usr/bin/env python3
"""Run every agent on fictitious data and write its page to output/ (plus an index), then open the index.

    python demo.py                 # all agents; asks before the Secretary writes
    python demo.py secretary       # one agent: secretary | habits | goals | career
    python demo.py --yes           # approve the Secretary's write without asking (scripts, CI)
    python demo.py --no-open       # do not open a browser
    python demo.py --live          # call Claude for any answer not recorded yet (needs ANTHROPIC_API_KEY)

No API key needed: the model's answers were recorded on a live run and replay. Nothing touches a real account.
"""

from __future__ import annotations

import json
import sys
import webbrowser
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from personal_ai_agents import pages  # noqa: E402
from personal_ai_agents.career import page as career_page  # noqa: E402
from personal_ai_agents.career import triage  # noqa: E402
from personal_ai_agents.goals import panel  # noqa: E402
from personal_ai_agents.habits import dashboard, loop  # noqa: E402
from personal_ai_agents.llm.client import LLM  # noqa: E402
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


def approve_from(argv: list[str]):
    def approve() -> bool:
        """--yes approves; otherwise ask, and treat no keyboard (pipe, CI, script) as "not approved"."""
        if "--yes" in argv:
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


def secretary(argv: list[str], verbose: bool) -> str:
    board = json.loads((DATA / "demo_board.json").read_text(encoding="utf-8"))
    llm = LLM(mode="auto" if "--live" in argv else "demo", max_calls=8)
    r = secretary_run.run(board, llm, approve_from(argv), say if verbose else quiet)
    (OUT / "secretary.html").write_text(secretary_page.page(r), encoding="utf-8")
    if verbose:
        say("Trace", table(r["trace"]))
        t = r["total"]
        print(f"\n{t['api_calls']} API call(s) now (US$ {t['cost_usd']:.5f}); {t['recorded_answers']} recorded "
              f"answer(s) replayed (they cost US$ {t['recorded_cost_usd']:.5f} when recorded).")  # fmt: skip
    if verbose or "--yes" in argv:
        print(f"{r['written']} task(s) written" if r["written"] else "nothing written: not approved")
    return f"a bad batch blocked by the gate; the plan closed in round {len(r['rounds'])}, then waits for approval"


def habit_data():
    export = DATA / "loop-habits-export.zip"
    if not export.exists():
        loop.write_fictitious_export(export, EXPORT_END)
    habits, marks = loop.read_export(export)
    return export, habits, marks


def habits(argv: list[str], verbose: bool) -> str:
    export, hab, marks = habit_data()
    rows = dashboard.summary(hab, marks, EXPORT_END)
    dashboard.write_spreadsheet(OUT / "habits.xlsx", hab, marks, rows, EXPORT_END)
    page = dashboard.page(rows, marks, EXPORT_END, f"data/{export.name}", "output/habits.xlsx")
    (OUT / "habits.html").write_text(page, encoding="utf-8")
    green = sum(1 for r in rows if dashboard.light(r["r30"]) == "ok")
    return f"{len(rows)} habits from the app export; {green} on target over the last 30 days"


def goals(argv: list[str], verbose: bool) -> str:
    _, _, marks = habit_data()
    g = json.loads((DATA / "goals.json").read_text(encoding="utf-8"))
    results = panel.evaluate(g, marks, EXPORT_END)
    (OUT / "goals.html").write_text(panel.page(g, results, EXPORT_END), encoding="utf-8")
    behind = sum(1 for o in results for k in o["krs"] if k["status"] != "ok")
    return f"{len(results)} goals, {behind} key result(s) behind or off track"


def career(argv: list[str], verbose: bool) -> str:
    snap = json.loads((DATA / "job_board_snapshot.json").read_text(encoding="utf-8"))
    profile = json.loads((DATA / "triage_profile.json").read_text(encoding="utf-8"))
    llm = LLM(mode="auto" if "--live" in argv else "demo", max_calls=25)
    store: dict = {}
    counts = triage.triage(snap["state"], store, profile, llm, snap["date"], llm.max_calls)
    page = career_page.page(store, counts, {"api_calls": llm.calls}, profile, snap["date"])
    (OUT / "career.html").write_text(page, encoding="utf-8")
    by = {d: sum(1 for r in store.values() if r.get("decision") == d) for d in ("apply", "monitor", "discard")}
    return f"{counts['new']} openings: {by['apply']} apply, {by['monitor']} monitor, {by['discard']} discard"


AGENTS = {"secretary": secretary, "habits": habits, "goals": goals, "career": career}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(exist_ok=True)
    chosen = [a for a in argv if a in AGENTS] or list(AGENTS)
    status = {}
    for name in chosen:
        status[name] = AGENTS[name](argv, verbose=len(chosen) == 1)
        print(f"{name:<10} {status[name]}  ->  output/{name}.html")
    if len(chosen) == len(AGENTS):
        (OUT / "index.html").write_text(pages.index(status), encoding="utf-8")
    target = OUT / ("index.html" if len(chosen) > 1 else f"{chosen[0]}.html")
    print(f"\nOpen {target.relative_to(ROOT)}")
    if "--no-open" not in argv:
        webbrowser.open(target.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
