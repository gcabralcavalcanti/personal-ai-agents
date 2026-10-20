"""HTML page for the Secretary demo: the blocked attempt, each planner round with the validator's verdict, the
validated plan as a day timeline, the approval and the gate."""

from __future__ import annotations

from datetime import date

from personal_ai_agents.pages import esc, shell
from personal_ai_agents.tracing import view

DAY_START, DAY_END = 7 * 60, 23 * 60

CSS = """
.days{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.tl{position:relative;height:560px;border-left:1px solid var(--line);margin-left:38px}
.tl .h{position:absolute;left:-38px;font-size:11px;color:var(--muted);transform:translateY(-6px)}
.tl .hl{position:absolute;left:0;right:0;border-top:1px dashed var(--line)}
.tl .b{position:absolute;left:6px;right:4px;border-radius:6px;padding:2px 7px;font-size:12.5px;overflow:hidden;
background:var(--chip);border-left:3px solid var(--accent)}
.tl .b.new{border-left-color:var(--ok);background:var(--okbg)}
.tl .b.moved{border-left-color:var(--warn);background:var(--warnbg)}
.round{border-left:4px solid var(--line);padding-left:12px;margin:10px 0}.round.ok{border-color:var(--ok)}
.round.open{border-color:var(--bad)}
"""


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _timeline(day: dict, board: dict) -> str:
    before = {it["content"]: (d, it["start"]) for d, items in board["days"].items() for it in items}
    before.update({o["content"]: (o["dueDate"], None) for o in board["overdue"]})  # overdue tasks were moved
    scale = 560 / (DAY_END - DAY_START)
    marks = "".join(
        f'<div class="hl" style="top:{(h * 60 - DAY_START) * scale:.0f}px"></div>'
        f'<div class="h" style="top:{(h * 60 - DAY_START) * scale:.0f}px">{h:02d}:00</div>'
        for h in range(7, 24, 2)
    )
    blocks = []
    for it in day["items"]:
        top = (_minutes(it["start"]) - DAY_START) * scale
        height = max(18, it["duration_min"] * scale)
        was = before.get(it["content"])
        kind = "new" if was is None else "moved" if was != (day["date"], it["start"]) else ""
        note = " · new" if kind == "new" else " · moved" if kind == "moved" else ""
        blocks.append(
            f'<div class="b {kind}" style="top:{top:.0f}px;height:{height:.0f}px">{esc(it["start"])} '
            f"{esc(it['content'])}<small>{note}</small></div>"
        )
    weekday = date.fromisoformat(day["date"]).strftime("%a")
    return f'<div class="panel"><b>{weekday} {esc(day["date"])}</b><div class="tl">{marks}{"".join(blocks)}</div></div>'


def page(r: dict) -> str:
    board = r["board"]
    first = r["first_try"]
    parts = [
        f'<div class="panel"><b>Request:</b> “{esc(board["request"])}”<br><small>Board on {esc(board["today"])}, '
        f"{esc(board['now'])}; one task is overdue; a dependency and a deadline apply.</small></div>",
        "<h2>1 · The model tries to write straight away</h2>",
        f'<div class="panel"><span class="badge bad">blocked, exit {first["exit"]}</span> '
        f"<code>{esc(first['call']['tool_name'])}</code><pre>{esc(first['message'])}</pre></div>",
        "<h2>2 · Planner rounds and the validator</h2>",
    ]
    for rd in r["rounds"]:
        seen = (
            "only the day named in the request" if rd["scope"] == "day" else "the whole board + the validator's report"
        )
        badge = (
            '<span class="badge ok">batch closed</span>' if rd["ok"] else '<span class="badge bad">batch open</span>'
        )
        summary, report = esc(rd["proposal"]["summary"]), esc(rd["report"])
        parts.append(
            f'<div class="round {"ok" if rd["ok"] else "open"}"><b>Round {rd["round"]}</b> (sees {seen}) '
            f"{badge}<p class=muted>{summary}</p><pre>{report}</pre></div>"
        )
    if r["closed"]:
        parts.append("<h2>3 · The validated plan</h2>")
        days = sorted(r["closed"]["days"], key=lambda d: d["date"])
        parts.append(f'<div class="days">{"".join(_timeline(d, board) for d in days)}</div>')
        parts.append("<h2>4 · Approval and the gate</h2>")
        if r["approved"]:
            rows = "".join(
                f"<tr><td><code>{esc(c['tool_name'].split('__')[-1])}</code></td><td>{len(c['tool_input']['tasks'])}"
                f'</td><td><span class="badge ok">exit {res[0]}: passed</span></td></tr>'
                for c, res in zip(r["calls"], r["hook_results"], strict=True)
            )
            parts.append(
                f'<div class="panel"><p>Approved. The same hook now lets the exact calls through; '
                f"{r['written']} task(s) written to the fake board.</p><table><tr><th>Call</th>"
                f"<th>Tasks</th><th>Hook</th></tr>{rows}</table></div>"
            )
        else:
            parts.append(
                '<div class="panel"><span class="badge warn">waiting for approval</span> Nothing written. '
                "Run <code>python demo.py secretary --yes</code> to approve.</div>"
            )
    trace = view.table_html(r["trace"])
    parts.append(f'<h2>Trace of this run</h2><div class="panel" style="overflow-x:auto">{trace}</div>')
    lead = (
        "A request goes through the planner (Claude), a validator written in code, your approval and a gate that "
        "physically blocks writes to the task manager until the whole batch has passed. Round 1 reproduces the "
        "error that created the gate: the planner looks only at the day the request names."
    )
    return shell("secretary", "Secretary (Todoist)", lead, "".join(parts), CSS)
