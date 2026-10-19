#!/usr/bin/env python3
"""check_batch.py - multi-day batch validator: the "validate before write" gate of the Todoist Secretary.

Why it exists: the agent used to validate one day at a time, and the failure that hurt most was multi-day
("fixed Sunday, left Monday and Tuesday broken"). This script takes the WHOLE proposed batch, checks every
day it touches plus the rules that only exist BETWEEN days, and returns one verdict with an exit code.
Exit 0 = batch CLOSED: it writes the GATE-OK flag that gate_hook.py requires before any add/reschedule.

This is a SIMPLIFIED, self-contained re-implementation for the public repo. The production checker has
~40 domain rules (meal order, focus blocks, travel time, ...) spread over several modules; the structure
below - per-day checks, cross-day checks, decisions for the human, one exit code - is the same.

Per-day checks
  OVERLAP      two timed items overlap (items marked "timebox": true accept items inside them)
  PAST         an item for today starts before "now"
  NIGHT        an item ends after the day's sleep_start
  BUDGET       planned hours exceed the day's budget_hours -> a pruning DECISION for the human
Cross-day checks
  PAST_DIRTY   the board still has overdue tasks (nothing may be left behind in the past)
  DAY_IN_PAST  the batch plans a date before today
  COVERAGE     a day declared as touched is missing from the batch
  DEP_CROSSDAY a task that depends on another is scheduled too early (lead time, in days)
  PIN_DRIFT    a task pinned "no later than" a date drifted past it

Usage:  python src/todoist_gate/check_batch.py <batch.json> [--json] [--no-gate]
Input format: see examples/batch_ok.json.
"""

import json
import os
import sys
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLAGS = os.environ.get("GATE_FLAGS_DIR") or os.path.join(REPO, ".flags")


def to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def d(iso):
    return date.fromisoformat(iso)


def shape_errors(batch):
    """Minimal structural validation before any rule runs (a JSON Schema is the planned next step)."""
    errs = []
    for k in ("today", "now", "days"):
        if k not in batch:
            errs.append(f"SHAPE: missing top-level field '{k}'")
    for i, day in enumerate(batch.get("days", [])):
        if "date" not in day:
            errs.append(f"SHAPE: days[{i}] has no 'date'")
        for j, it in enumerate(day.get("items", [])):
            if not isinstance(it.get("content"), str):
                errs.append(f"SHAPE: days[{i}].items[{j}] has no 'content'")
            if "start" in it and not isinstance(it.get("duration_min"), int):
                errs.append(f"SHAPE: days[{i}].items[{j}] has 'start' but no integer 'duration_min'")
    return errs


def check_day(day, today, now):
    errors, decisions = [], []
    dt = day["date"]
    timed = sorted((it for it in day.get("items", []) if it.get("start")), key=lambda it: to_min(it["start"]))
    spans = [(to_min(it["start"]), to_min(it["start"]) + it["duration_min"], it) for it in timed]
    for i, (_a0, a1, a) in enumerate(spans):
        for b0, b1, b in spans[i + 1 :]:
            if b0 >= a1:
                break
            if a.get("timebox") and b1 <= a1:
                continue  # a timebox block accepts small tasks inside it
            errors.append(f'OVERLAP: "{a["content"]}" ({a["start"]}) x "{b["content"]}" ({b["start"]})')
    if dt == today and now:
        for s, _, it in spans:
            if s < to_min(now):
                errors.append(f'PAST: "{it["content"]}" starts {it["start"]}, before now ({now})')
    if day.get("sleep_start"):
        for _, e, it in spans:
            if e > to_min(day["sleep_start"]):
                errors.append(f'NIGHT: "{it["content"]}" ends after sleep_start ({day["sleep_start"]})')
    budget = day.get("budget_hours")
    if budget:
        boxes = [(s, e) for s, e, it in spans if it.get("timebox")]
        used = sum(
            e - s
            for s, e, it in spans  # items inside a timebox are already counted by the box
            if it.get("timebox") or not any(b0 <= s and e <= b1 for b0, b1 in boxes)
        )
        if used > budget * 60:
            decisions.append(f"[{dt}] BUDGET: {used / 60:.1f}h planned > {budget}h - which task gets pruned?")
    return errors, decisions


def check_batch(batch):
    shape = shape_errors(batch)
    if shape:
        return {"ok": False, "days": [], "blockers": shape, "decisions": []}
    today, now = batch["today"], batch.get("now")
    blockers, decisions, per_day = [], [], []

    for day in batch["days"]:
        errs, decs = check_day(day, today, now)
        per_day.append({"date": day["date"], "errors": errs, "ok": not errs and not decs})
        decisions += decs

    overdue = batch.get("overdue") or []
    if overdue:
        sample = "; ".join(f'"{o["content"]}" ({o["dueDate"]})' for o in overdue[:5])
        blockers.append(f"PAST_DIRTY: {len(overdue)} overdue task(s) still on the board: {sample}")
    for day in batch["days"]:
        if d(day["date"]) < d(today):
            blockers.append(f"DAY_IN_PAST: {day['date']} is before today ({today})")

    missing = sorted(set(batch.get("days_touched") or []) - {x["date"] for x in batch["days"]})
    if missing:
        blockers.append(f"COVERAGE: touched day(s) not in the batch: {', '.join(missing)}")

    where = {}
    for day in batch["days"]:
        for it in day.get("items", []) + day.get("untimed", []):
            where.setdefault(it["content"].lower(), day["date"])
    for dep in batch.get("dependencies") or []:
        a, b = where.get(dep["before"].lower()), where.get(dep["after"].lower())
        if a and b and d(b) < d(a) + timedelta(days=dep.get("lead_days", 0)):
            blockers.append(
                f'DEP_CROSSDAY: "{dep["after"]}" ({b}) needs "{dep["before"]}" ({a}) first, '
                f"lead time {dep.get('lead_days', 0)} day(s) - {dep.get('reason', '')}"
            )
            decisions.append(f'[{b}] DEPENDENCY: move "{dep["after"]}" or bring "{dep["before"]}" forward?')

    for pin in batch.get("pins") or []:
        got = where.get(pin["content"].lower())
        if got and d(got) > d(pin["no_later_than"]):
            blockers.append(f'PIN_DRIFT: "{pin["content"]}" landed on {got}, after its pin {pin["no_later_than"]}')

    ok = all(p["ok"] for p in per_day) and not blockers and not decisions
    return {"ok": ok, "days": per_day, "blockers": blockers, "decisions": decisions}


def report(res):
    lines = ["STATUS PER DAY"]
    for p in res["days"]:
        lines.append(f"  {'OK  ' if p['ok'] else 'OPEN'} {p['date']}" + "".join(f"\n       - {e}" for e in p["errors"]))
    for title, key in (("GLOBAL BLOCKERS", "blockers"), ("DECISIONS FOR THE HUMAN", "decisions")):
        if res[key]:
            lines += ["", title] + [f"  - {x}" for x in res[key]]
    lines += ["", "BATCH CLOSED - safe to write." if res["ok"] else "BATCH OPEN - do not write, do not report done."]
    return "\n".join(lines)


def open_gate():
    os.makedirs(FLAGS, exist_ok=True)
    p = os.path.join(FLAGS, "GATE-OK")
    open(p, "w").close()
    os.utime(p, None)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    with open(args[0], encoding="utf-8") as f:
        res = check_batch(json.load(f))
    print(report(res))
    if "--json" in argv:
        print(json.dumps(res, indent=1))
    if res["ok"] and "--no-gate" not in argv:
        open_gate()
        print("gate open for 15 min (add-tasks / reschedule-tasks)")
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
