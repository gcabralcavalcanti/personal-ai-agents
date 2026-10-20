"""HTML page for the flashcards x calendar demo: forecast, contract check, the blocked and the accepted plan."""

from __future__ import annotations

from datetime import date, timedelta

from personal_ai_agents.pages import esc, shell
from personal_ai_agents.study.plan import day_items

COLORS = ["#3b5bdb", "#2b8a3e", "#e8590c", "#ae3ec9", "#868e96", "#1098ad"]

CSS = """
.chart{width:100%;max-width:640px}.legend span{display:inline-block;margin-right:12px;font-size:13px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
.week{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.col h4{margin:0 0 6px;font-size:13px}.col div{font-size:12.5px;padding:2px 6px;margin-bottom:3px;border-radius:5px;
background:var(--chip);color:var(--muted)}.col .study{color:var(--fg);border-left:3px solid var(--accent)}
.col .new{background:var(--okbg);color:var(--fg);border-left:3px solid var(--ok)}
"""


def chart(loads: dict[str, list[int]], start: date) -> str:
    decks = list(loads)
    days = len(next(iter(loads.values())))
    totals = [sum(loads[d][i] for d in decks) for i in range(days)]
    top = max(totals) or 1
    w, h, bar = 640, 220, 60
    parts = []
    for i in range(days):
        y = h - 20
        for k, d in enumerate(decks):
            v = loads[d][i] * (h - 40) / top
            y -= v
            parts.append(
                f'<rect x="{30 + i * 85}" y="{y:.1f}" width="{bar}" height="{v:.1f}" fill="{COLORS[k % 6]}">'
                f"<title>{esc(d)}: {loads[d][i]} min</title></rect>"
            )
        label = (start + timedelta(days=i)).strftime("%a")
        parts.append(
            f'<text x="{60 + i * 85}" y="{h - 4}" text-anchor="middle" font-size="12" fill="currentColor">'
            f"{label}</text>"
        )
        parts.append(
            f'<text x="{60 + i * 85}" y="{h - 24 - totals[i] * (h - 40) / top:.0f}" text-anchor="middle" '
            f'font-size="11" fill="currentColor">{totals[i]}m</text>'
        )
    legend = "".join(f'<span><i style="background:{COLORS[k % 6]}"></i>{esc(d)}</span>' for k, d in enumerate(decks))
    return (
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="minutes of review per day">'
        f'{"".join(parts)}</svg><div class="legend">{legend}</div>'
    )


def week_grid(week: dict, blocks: list[dict]) -> str:
    start = date.fromisoformat(week["start"])
    study = {b["content"] for b in week["fixed"] if b.get("deck") not in (None, "-")}
    cols = []
    for i in range(7):
        items = [(it, "study" if it["content"] in study else "") for it in day_items(week, i)]
        items += [(b, "new") for b in blocks if b["day"] == i]
        items.sort(key=lambda x: x[0]["start"])
        rows = "".join(
            f'<div class="{kind}">{esc(it["start"])} · {it["duration_min"]}m {esc(it["content"])}</div>'
            for it, kind in items
        )
        d = start + timedelta(days=i)
        cols.append(f'<div class="col"><h4>{d:%a} {d:%d/%m}</h4>{rows}</div>')
    return f'<div class="panel"><div class="week">{"".join(cols)}</div></div>'


def page(r: dict) -> str:
    week, a = r["week"], r["audit"]
    start = date.fromisoformat(week["start"])
    got = {b["deck"] for b in r["rounds"][-1]["blocks"]}
    audit_rows = (
        [
            f"<li><b>{esc(d)}</b> has cards due and no block opens it: "
            + (
                "a block is proposed.</li>"
                if d in got
                else "too few cards this week for a block (under 5 min a day); it still needs one, your call.</li>"
            )
            for d in a["orphans"]
        ]
        + [
            f"<li><b>{esc(b)}</b> points to a deck that does not exist: fix the line by hand.</li>"
            for b in a["missing_deck"]
        ]
        + [f"<li><b>{esc(b)}</b> is a study block with no <code>deck:</code> line.</li>" for b in a["no_deck_line"]]
    )
    short = "".join(
        f"<li><b>{esc(s['block'])}</b> on {(start + timedelta(days=s['day'])):%a}: {s['block_min']} min booked, "
        f"{s['load_min']} min of cards due. Lengthen it? (your call; nothing changes on its own)</li>"
        for s in r["shortfalls"]
    )
    parts = [
        "<h2>1 · How much review is coming</h2>",
        f'<div class="panel">{chart(r["load"], start)}<p class="muted">Minutes per day = cards due x '
        f"{week['seconds_per_review']} s + new cards x {week['seconds_per_new']} s (the averages from the review "
        "history).</p></div>",
        "<h2>2 · Does every deck have a block that opens it?</h2>",
        f'<div class="panel"><ul>{"".join(audit_rows)}</ul>'
        + (f"<p><b>Blocks shorter than their load</b></p><ul>{short}</ul>" if short else "")
        + "</div>",
        "<h2>3 · Proposed blocks, checked before anything is written</h2>",
    ]
    for rd in r["rounds"]:
        badge = (
            '<span class="badge ok">batch closed</span>' if rd["ok"] else '<span class="badge bad">batch open</span>'
        )
        title = "Naive plan: every new block at 21:00" if rd["naive"] else "Fitted plan: first free slot of each day"
        lines = rd["report"].splitlines()
        if rd["ok"]:
            lines = [ln for ln in lines if ln.startswith("BATCH")] or lines[-1:]
        else:
            problems = [ln.strip()[2:] for ln in lines if ln.strip().startswith("- ")]
            lines = problems[:4] + ([f"... and {len(problems) - 4} more"] if len(problems) > 4 else [])
        report = esc("\n".join(lines))
        parts.append(f'<div class="panel" style="margin-bottom:10px"><b>{title}</b> {badge}<pre>{report}</pre></div>')
    final = r["rounds"][-1]
    if final["ok"]:
        parts.append("<h2>4 · The week with the new blocks (green)</h2>" + week_grid(week, final["blocks"]))
        tasks = r["calls"][0]["tool_input"]["tasks"] if r["calls"] else []
        rows = "".join(
            f"<tr><td>{esc(t['content'])}</td><td>{esc(t['dueString'])}</td><td class=n>{t['duration']}"
            f"</td><td><code>{esc(t['description'])}</code></td></tr>"
            for t in tasks
        )
        if r["approved"]:
            gate = ", ".join(f"exit {code}" for code, _ in r["hook"])
            status = f'<span class="badge ok">approved; the gate let the call through ({gate})</span>'
        else:
            status = '<span class="badge warn">waiting for approval</span> run with <code>--yes</code>'
        parts.append(
            f'<h2>5 · The batch for the task manager</h2><div class="panel">{status}<table><tr><th>Task</th>'
            f"<th>When</th><th class=n>min</th><th>Description</th></tr>{rows}</table></div>"
        )
    lead = (
        "The flashcard side reports how many cards fall due in each deck; the calendar side finds room for them. "
        "Each deck gets exactly one block that opens it, the new blocks go through the same checker and gate as any "
        "other write, and nothing is written without approval. Fictitious decks and week."
    )
    return shell("study", "Study blocks (flashcards x calendar)", lead, "".join(parts), CSS)
