#!/usr/bin/env python3
"""view.py - read a trace.jsonl and show it: a table in the terminal, or a static HTML page.

Usage:  python personal_ai_agents/tracing/view.py output/runs/<run>/trace.jsonl            # terminal table
        python personal_ai_agents/tracing/view.py output/runs/<run>/trace.jsonl --html out.html
        python personal_ai_agents/tracing/view.py --last                             # newest run under output/runs/
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLS = [
    ("stage", "Stage", 34),
    ("status", "Status", 8),
    ("duration_ms", "ms", 7),
    ("api_calls", "Calls", 5),
    ("recorded_answers", "Replay", 6),
    ("input_tokens", "Tok in", 7),
    ("output_tokens", "Tok out", 7),
    ("cost_usd", "US$ now", 9),
    ("recorded_cost_usd", "US$ rec.", 9),
    ("detail", "Detail", 46),
]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label(r: dict) -> str:
    extra = " ".join(f"{k}={r[k]}" for k in ("round", "case", "opening") if k in r)
    return f"{r['stage']} {extra}".strip()


def table(rows: list[dict]) -> str:
    def cell(r, key, width):
        v = label(r) if key == "stage" else r.get(key, "")
        v = f"{v:.5f}" if key.endswith("cost_usd") and isinstance(v, (int, float)) else str(v)
        return v[: width - 1] + "…" if len(v) > width else v.ljust(width)

    out = ["  ".join(h.ljust(w) for _, h, w in COLS), "  ".join("-" * w for _, _, w in COLS)]
    for r in rows:
        if r["stage"] == "run":
            out.append("  ".join("-" * w for _, _, w in COLS))
        out.append("  ".join(cell(r, k, w) for k, _, w in COLS))
    return "\n".join(out)


def _fmt(r: dict, key: str) -> str:
    v = label(r) if key == "stage" else r.get(key, "")
    return f"{v:.5f}" if key.endswith("cost_usd") and isinstance(v, (int, float)) else str(v)


def table_html(rows: list[dict]) -> str:
    """The trace as an HTML table with a duration bar per stage (used on its own page and inside demo pages)."""
    longest = max((r.get("duration_ms", 0) for r in rows if r["stage"] != "run"), default=1) or 1
    colors = {"ok": "#2f855a", "blocked": "#b7791f", "error": "#c53030", "skipped": "#718096"}
    body = []
    for r in rows:
        width = max(2, 100 * r.get("duration_ms", 0) // longest)
        color = colors.get(r["status"], "#4a5568")
        bar = "" if r["stage"] == "run" else f'<div class="tbar" style="width:{width}%;background:{color}"></div>'
        tds = "".join(f"<td>{html.escape(_fmt(r, k))}</td>" for k, _, _ in COLS)
        body.append(f'<tr class="{r["status"]} {"total" if r["stage"] == "run" else ""}">{tds}<td>{bar}</td></tr>')
    heads = "".join(f"<th>{h}</th>" for _, h, _ in COLS)
    return f'<table class="trace"><tr>{heads}<th>Duration</th></tr>{"".join(body)}</table>'


def page(rows: list[dict], title: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>
:root{{--bg:#fff;--fg:#1a202c;--line:#e2e8f0;--muted:#718096}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171923;--fg:#e2e8f0;--line:#2d3748;--muted:#a0aec0}}}}
body{{font:14px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:24px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:6px 8px;border-bottom:1px solid var(--line);
text-align:left;vertical-align:top}}
th{{color:var(--muted);font-weight:600}}td:nth-child(n+3):nth-child(-n+9){{text-align:right;font-variant-numeric:tabular-nums}}
.tbar{{height:10px;border-radius:3px;min-width:4px}}td:last-child{{width:18%}}
tr.blocked td:nth-child(2){{color:#b7791f;font-weight:600}}tr.error td:nth-child(2){{color:#c53030;font-weight:600}}
tr.total td{{font-weight:600;border-top:2px solid var(--fg)}}
</style></head><body><h1>{html.escape(title)}</h1>{table_html(rows)}
</body></html>"""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--last" in argv:
        runs = sorted((ROOT / "output" / "runs").glob("*/trace.jsonl"), key=lambda p: p.stat().st_mtime)
        if not runs:
            print("no runs yet")
            return 1
        path = runs[-1]
    else:
        args = [a for a in argv if not a.startswith("--")]
        if not args:
            print(__doc__)
            return 2
        path = Path(args[0])
    rows = load(path)
    if "--html" in argv:
        out = Path(argv[argv.index("--html") + 1])
        run_id = next((r["run_id"] for r in rows if r.get("run_id")), path.parent.name)
        out.write_text(page(rows, f"Trace {run_id}"), encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
