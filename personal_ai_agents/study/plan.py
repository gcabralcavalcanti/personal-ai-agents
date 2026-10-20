"""Flashcards x calendar: turn the review forecast into study blocks that fit the week, through the same gate.

Three rules from my own setup:
  - a deck is a button: every active deck has exactly one block that opens it, and a study block says which deck
    on a `deck:` line (a production block says `deck: -`);
  - the load comes from the forecast (cards due x seconds per card), never from a guess;
  - new blocks are a proposal: the batch passes the same validator and gate as any other write.
"""

from __future__ import annotations

import math
import tempfile
from datetime import date, timedelta

from personal_ai_agents.todoist_gate import check_batch
from personal_ai_agents.todoist_gate.run import hook

MIN_BLOCK = 10


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def load(week: dict) -> dict[str, list[int]]:
    """Minutes of review per deck per day: due x seconds per review + new cards x seconds per new card."""
    spr, spn = week["seconds_per_review"], week["seconds_per_new"]
    return {f["deck"]: [math.ceil((d * spr + f["new_per_day"] * spn) / 60) for d in f["due"]] for f in week["forecast"]}


def audit(week: dict) -> dict:
    """The contract: decks with cards but no block, blocks pointing to a deck that does not exist, study blocks
    with no deck line."""
    decks = {f["deck"] for f in week["forecast"]}
    opened = {b["deck"] for b in week["fixed"] if b.get("deck") not in (None, "-")}
    return {
        "orphans": sorted(d for d in decks if d not in opened),
        "missing_deck": sorted(
            {b["content"] for b in week["fixed"] if b.get("deck") not in (None, "-") and b["deck"] not in decks}
        ),
        "no_deck_line": sorted({b["content"] for b in week["fixed"] if "deck" not in b}),
    }


def day_items(week: dict, i: int) -> list[dict]:
    return [
        {"content": b["content"], "start": b["start"], "duration_min": b["duration_min"]}
        for b in week["fixed"]
        if i in b["days"]
    ]


def free_slot(items: list[dict], length: int, window: tuple[int, int]) -> int | None:
    """First start in the window where `length` minutes fit between existing items (5-minute grid)."""
    busy = sorted((minutes(it["start"]), minutes(it["start"]) + it["duration_min"]) for it in items)
    t = window[0]
    for s, e in [*busy, (window[1], window[1])]:
        if s - t >= length:
            return t
        t = max(t, e)
        t += -t % 5
    return None


def propose(week: dict, naive: bool = False) -> list[dict]:
    """One block per day for each orphan deck with load. The naive version puts every block at 21:00."""
    start = date.fromisoformat(week["start"])
    window = (minutes(week["window"][0]), minutes(week["window"][1]))
    loads = load(week)
    blocks = []
    for deck in audit(week)["orphans"]:
        for i, m in enumerate(loads[deck]):
            if m < 5:
                continue
            length = max(MIN_BLOCK, m + -m % 5)
            items = day_items(week, i) + [b for b in blocks if b["day"] == i]
            at = minutes("21:00") if naive else free_slot(items, length, window)
            if at is None:
                continue
            blocks.append(
                {
                    "day": i,
                    "date": (start + timedelta(days=i)).isoformat(),
                    "content": f"Cards: {deck}",
                    "start": hhmm(at),
                    "duration_min": length,
                    "deck": deck,
                }
            )
    return sorted(blocks, key=lambda b: (b["date"], b["start"]))


def batch(week: dict, blocks: list[dict]) -> dict:
    start = date.fromisoformat(week["start"])
    days = []
    for i in range(7):
        d = (start + timedelta(days=i)).isoformat()
        items = day_items(week, i) + [
            {k: b[k] for k in ("content", "start", "duration_min")} for b in blocks if b["day"] == i
        ]
        days.append(
            {"date": d, "budget_hours": week["budget_hours"], "sleep_start": week["sleep_start"], "items": items}
        )
    return {
        "today": week["start"],
        "now": week["now"],
        "days_touched": sorted({b["date"] for b in blocks}),
        "overdue": [],
        "days": days,
    }


def shortfalls(week: dict) -> list[dict]:
    """Existing blocks shorter than their deck's load: a decision for the human, never an automatic change."""
    loads = load(week)
    out = []
    for b in week["fixed"]:
        deck = b.get("deck")
        if deck in loads:
            for i in b["days"]:
                if loads[deck][i] > b["duration_min"]:
                    out.append(
                        {"block": b["content"], "day": i, "block_min": b["duration_min"], "load_min": loads[deck][i]}
                    )
    return out


def run(week: dict, approve) -> dict:
    """Naive plan -> validator; fitted plan -> validator -> approval -> gate. Returns everything for the page."""
    rounds = []
    for naive in (True, False):
        blocks = propose(week, naive)
        res = check_batch.check_batch(batch(week, blocks))
        rounds.append({"naive": naive, "blocks": blocks, "ok": res["ok"], "report": check_batch.report(res)})
        if res["ok"]:
            break
    final = rounds[-1]
    out = {
        "week": week,
        "load": load(week),
        "audit": audit(week),
        "shortfalls": shortfalls(week),
        "rounds": rounds,
        "calls": [],
        "approved": None,
        "hook": [],
    }
    if final["ok"]:
        flags = tempfile.mkdtemp(prefix="gate-flags-")
        check_batch.FLAGS = flags
        check_batch.open_gate()
        tasks = [
            {
                "content": b["content"],
                "dueString": f"{b['date']} at {b['start']}",
                "duration": b["duration_min"],
                "description": f"deck: {b['deck']}",
            }
            for b in final["blocks"]
        ]
        out["calls"] = [{"tool_name": "mcp__todoist__add-tasks", "tool_input": {"tasks": tasks}}]
        out["approved"] = approve()
        if out["approved"]:
            out["hook"] = [hook(c, flags) for c in out["calls"]]
    return out
