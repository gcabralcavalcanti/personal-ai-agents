#!/usr/bin/env python3
"""Read your Todoist tasks (read-only) into the board format the Secretary demo uses.

    TODOIST_API_TOKEN=... python personal_ai_agents/todoist_gate/todoist_export.py --days 3 > my_board.json
    python demo.py secretary --board my_board.json --request "move the weekly review to Thursday"

The token comes from the environment or `.env` (Todoist: Settings > Integrations > Developer). This script only
reads. In my own setup the writes go through Claude Code's Todoist connector, and the gate hook refuses them until
the validator passed; the demo's writes always go to a fake board.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

API = "https://api.todoist.com/api/v1/tasks/filter"
ROOT = Path(__file__).resolve().parents[2]


def token() -> str | None:
    if "TODOIST_API_TOKEN" in os.environ:
        return os.environ["TODOIST_API_TOKEN"] or None
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "TODOIST_API_TOKEN" and value.strip():
                return value.strip().strip('"')
    return None


def http_get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch(query: str, tok: str, get=http_get) -> list[dict]:
    tasks, cursor = [], ""
    while True:
        params = {"query": query, "limit": 200, **({"cursor": cursor} if cursor else {})}
        page = get(f"{API}?{urllib.parse.urlencode(params)}", tok)
        tasks += page.get("results", [])
        cursor = page.get("next_cursor")
        if not cursor:
            return tasks


def to_board(tasks: list[dict], today: date, now: str, budget_hours: int = 9, sleep_start: str = "23:00") -> dict:
    """Timed tasks go on their day; overdue ones are listed apart (the validator refuses a plan that ignores them)."""
    days: dict[str, list[dict]] = {}
    overdue = []
    for t in tasks:
        due = (t.get("due") or {}).get("date")
        if not due:
            continue
        day = date.fromisoformat(due[:10])
        if day < today:
            overdue.append({"id": t["id"], "content": t["content"], "dueDate": day.isoformat(), "duration_min": 15})
            continue
        if "T" not in due:
            continue  # untimed tasks do not occupy the calendar
        dur = t.get("duration") or {}
        minutes = dur.get("amount", 30) if dur.get("unit", "minute") == "minute" else 30
        start = datetime.fromisoformat(due.replace("Z", "+00:00")).strftime("%H:%M")
        days.setdefault(day.isoformat(), []).append(
            {"id": t["id"], "content": t["content"], "start": start, "duration_min": minutes}
        )
    for items in days.values():
        items.sort(key=lambda it: it["start"])
    return {
        "today": today.isoformat(),
        "now": now,
        "budget_hours": budget_hours,
        "sleep_start": sleep_start,
        "days": dict(sorted(days.items())),
        "overdue": overdue,
        "pins": [],
        "dependencies": [],
        "request": "",
        "request_day": today.isoformat(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read Todoist tasks into a board JSON (read-only).")
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args(argv)
    tok = token()
    if not tok:
        print("Set TODOIST_API_TOKEN (environment or .env).", file=sys.stderr)
        return 2
    today = date.today()
    end = today + timedelta(days=a.days - 1)
    tasks = fetch(f"overdue | due before: {end + timedelta(days=1):%Y-%m-%d}", tok)
    print(json.dumps(to_board(tasks, today, datetime.now().strftime("%H:%M")), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
