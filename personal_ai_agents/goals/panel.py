"""The quarter's goals against the data: each key result measured from its source, and the felt score next to it.

A key result is an artifact (it exists or not) or a series from a flow that already runs: the habit app or the task
manager. The highest-value finding is often the gap between how a goal feels and what the data shows.
"""

from __future__ import annotations

from datetime import date, timedelta

from personal_ai_agents.habits import loop
from personal_ai_agents.pages import esc, shell

CREDIT = {"ok": 1.0, "warn": 0.5, "bad": 0.0}  # the measured score: on track, behind, off track


def measure(kr: dict, marks: dict, end: date, start: date) -> dict:
    """Base (first 4 weeks), current value (last 4 weeks), target and status for one key result."""
    if kr["source"] == "artifact":
        status = "ok" if kr["done"] else "warn"
        return {
            "base": "",
            "now": "done" if kr["done"] else kr.get("progress", "not yet"),
            "target": "exists",
            "ratio": 1.0 if kr["done"] else 0.0,
            "status": status,
        }
    if kr["source"] == "task manager":
        ratio = kr["count"] / kr["target"]
        elapsed = max(0.05, min(1.0, (end - start).days / 92))
        status = "ok" if ratio >= elapsed else "warn" if ratio >= 0.6 * elapsed else "bad"
        return {"base": "0", "now": str(kr["count"]), "target": str(kr["target"]), "ratio": ratio, "status": status}
    m = marks[kr["habit"]]
    now = loop.rate(m, end, 28) or 0.0
    base = loop.rate(m, start + timedelta(days=27), 28) or 0.0
    ratio = now / kr["target"]
    status = "ok" if ratio >= 1 else "warn" if ratio >= 0.8 else "bad"
    return {
        "base": f"{base:.0%}",
        "now": f"{now:.0%}",
        "target": f"{kr['target']:.0%}",
        "ratio": ratio,
        "status": status,
    }


def evaluate(goals: dict, marks: dict, end: date) -> list[dict]:
    start = date.fromisoformat(goals["start"])
    out = []
    for obj in goals["objectives"]:
        krs = [{**kr, **measure(kr, marks, end, start)} for kr in obj["key_results"]]
        measured = round(10 * sum(CREDIT[k["status"]] for k in krs) / len(krs))
        out.append({"title": obj["title"], "felt": obj["felt"], "measured": measured, "krs": krs})
    return out


LABEL = {"ok": "on track", "warn": "behind", "bad": "off track"}


def page(goals: dict, results: list[dict], end: date) -> str:
    cards = []
    for o in results:
        gap = o["measured"] - o["felt"]
        note = ""
        if abs(gap) >= 3:
            note = (
                f'<p class="warn" style="margin:8px 0 0">The data says {"better" if gap > 0 else "worse"} than it '
                f"feels ({o['felt']}/10 felt, {o['measured']}/10 measured).</p>"
            )
        rows = "".join(
            f"<tr><td>{esc(k['text'])}<br><small>[{esc(k['source'])}]</small></td><td class=n>{esc(k['base'])}</td>"
            f"<td class=n><b>{esc(k['now'])}</b></td><td class=n>{esc(k['target'])}</td>"
            f'<td><span class="badge {k["status"]}">{LABEL[k["status"]]}</span></td></tr>'
            for k in o["krs"]
        )
        cards.append(
            f'<div class="panel"><h2 style="margin:0 0 4px">{esc(o["title"])}</h2>'
            f'<span class="chip">felt {o["felt"]}/10</span><span class="chip">measured {o["measured"]}/10</span>'
            "<table><tr><th>Key result</th><th class=n>Base</th><th class=n>Now</th>"
            "<th class=n>Target</th><th></th></tr>"
            f"{rows}</table>{note}</div>"
        )
    lead = (
        f"Quarter {esc(goals['quarter'])}, as of {end.isoformat()}. Each key result is measured from where it lives: "
        "the habit app (last 4 weeks against the first 4), the task manager, or a file that exists or not. "
        "Nothing here is typed by hand into a tracker."
    )
    return shell("goals", "Goals", lead, f'<div class="grid g2">{"".join(cards)}</div>')
