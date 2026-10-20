"""HTML page of triaged openings: what to apply to, what to watch, what was discarded and why."""

from __future__ import annotations

from personal_ai_agents.pages import esc, shell

ORDER = {"apply": 0, "monitor": 1, "discard": 2}
BADGE = {"apply": "ok", "monitor": "warn", "discard": "bad"}

CSS = """
.filters button{font:inherit;border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:999px;
padding:3px 12px;margin:0 6px 8px 0;cursor:pointer}.filters button.on{border-color:var(--accent)}
tr.hide{display:none}td a{color:inherit}
"""

SCRIPT = """<script>
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.filters button').forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('tr[data-d]').forEach(r => r.classList.toggle('hide', f !== 'all' && r.dataset.d !== f));
}));
</script>"""


def page(store: dict, counts: dict, summary: dict, profile: dict, snapshot_date: str) -> str:
    rows = sorted(store.values(), key=lambda r: (ORDER.get(r.get("decision"), 3), r["company"], r["title"]))
    by = {d: sum(1 for r in rows if r.get("decision") == d) for d in ORDER}
    tiles = [
        (counts["new"], "new openings on the boards"),
        (counts["by_code"], "decided by code, no model call"),
        (counts["by_model"], "decided by the model"),
        (summary["api_calls"], "model calls in this run (recorded answers replayed)"),
    ]
    tiles_html = "".join(
        f'<div class="panel tile"><div class="v">{v}</div><div class="l">{esc(lbl)}</div></div>' for v, lbl in tiles
    )
    buttons = '<button data-f="all" class="on">All</button>' + "".join(
        f'<button data-f="{d}">{d.title()} ({by[d]})</button>' for d in ORDER
    )
    trs = "".join(
        f'<tr data-d="{esc(r.get("decision"))}"><td><span class="badge {BADGE.get(r.get("decision"), "")}">'
        f"{esc(r.get('decision'))}</span></td><td>{esc(r['company'])}</td>"
        f'<td><a href="{esc(r["url"])}">{esc(r["title"])}</a></td><td>{esc(r.get("geography", ""))}</td>'
        f"<td>{esc(r.get('reason', ''))}<br><small>decided by {esc(r.get('decided_by', ''))}</small></td></tr>"
        for r in rows
    )
    table = (
        f'<div class="panel" style="overflow-x:auto"><div class="filters">{buttons}</div><table><tr><th></th>'
        f"<th>Company</th><th>Opening</th><th>Place</th><th>Why</th></tr>{trs}</table></div>"
    )
    geo = profile["geography"]
    lead = (
        f"New openings on public job boards (saved on {esc(snapshot_date)}) plus four fictitious ones that state "
        "their graduation dates (marked as such), sorted for an example candidate: "
        f"{esc(profile['candidate'])}; preferred city {esc(', '.join(geo['preferred']))}; also "
        f"{esc(', '.join(geo['acceptable']))}. Code discards senior and mid-level titles without calling the model; "
        "the model reads the rest and every answer is checked against the rules (an opening outside the geography "
        "is never 'apply'). Real titles rarely state graduation dates, so most of them land on 'monitor' until the "
        "posting is read. Running it again costs nothing: verdicts are stored by opening."
    )
    return shell(
        "career",
        "Career",
        lead,
        f'<div class="grid g4">{tiles_html}</div><h2>Openings</h2>{table}{SCRIPT}',
        CSS,
        data_note="Public job-board titles plus four fictitious openings; example candidate profile.",
    )
