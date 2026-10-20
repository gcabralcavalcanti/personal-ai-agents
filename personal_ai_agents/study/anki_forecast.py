#!/usr/bin/env python3
"""Read the review forecast of your Anki decks (read-only) into the `forecast` list of a study week.

    python personal_ai_agents/study/anki_forecast.py "Languages" "Statistics" > forecast.json

Needs Anki open with the AnkiConnect add-on (code 2055492159). Only reading actions are sent; paste the result
into your copy of data/study_week.json and run `python demo.py study --week my_week.json`.
"""

from __future__ import annotations

import json
import sys
import urllib.request

URL = "http://127.0.0.1:8765"
READ_ONLY = {"deckNames", "findCards", "getDeckConfig"}


def http_post(action: str, params: dict) -> object:
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(URL, body), timeout=10) as r:
        reply = json.loads(r.read().decode("utf-8"))
    if reply.get("error"):
        raise RuntimeError(f"AnkiConnect {action}: {reply['error']}")
    return reply["result"]


def forecast(decks: list[str], days: int = 7, post=http_post) -> list[dict]:
    """Cards due per day (today includes overdue) and the deck's daily new-card limit."""

    def ask(action: str, **params):
        if action not in READ_ONLY:
            raise PermissionError(action)
        return post(action, params)

    known = set(ask("deckNames"))
    out = []
    for deck in decks:
        if deck not in known:
            raise SystemExit(f"no deck named {deck!r} in this collection")
        q = f'"deck:{deck}"'
        due = [len(ask("findCards", query=f"{q} is:due"))]
        due += [len(ask("findCards", query=f"{q} prop:due={i}")) for i in range(1, days)]
        waiting = len(ask("findCards", query=f"{q} is:new -is:suspended"))
        per_day = ask("getDeckConfig", deck=deck)["new"]["perDay"]
        out.append({"deck": deck, "due": due, "new_per_day": min(per_day, waiting)})
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(json.dumps(forecast(sys.argv[1:]), ensure_ascii=False, indent=1))
