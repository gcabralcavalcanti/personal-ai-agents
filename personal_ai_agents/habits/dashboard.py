"""Habit-tracker export -> spreadsheet (the database) and an HTML dashboard with 14/30/90-day views."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from personal_ai_agents.habits import loop
from personal_ai_agents.pages import esc, shell

GOOD, FAIR = 0.70, 0.50  # traffic lights on the 30-day rate
WINDOWS = (14, 30, 90)


def light(r: float | None) -> str:
    if r is None:
        return ""
    return "ok" if r >= GOOD else "warn" if r >= FAIR else "bad"


def pct(r: float | None) -> str:
    return "" if r is None else f"{r:.0%}"


def summary(habits: list[dict], marks: dict, end: date) -> list[dict]:
    rows = []
    for h in habits:
        m = marks[h["Name"]]
        rates = {w: loop.rate(m, end, w) for w in WINDOWS}
        rows.append(
            {
                "name": h["Name"],
                "color": h["Color"],
                **{f"r{w}": rates[w] for w in WINDOWS},
                "streak": loop.streak(m, end),
                "weekly": loop.weekly(m, end),
            }
        )
    return rows


def write_spreadsheet(path: Path, habits: list[dict], marks: dict, rows: list[dict], end: date, days: int = 90) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Habit", "14 days", "30 days", "90 days", "Current streak"])
    for r in rows:
        ws.append(
            [r["name"], *(round(r[f"r{w}"], 3) if r[f"r{w}"] is not None else None for w in WINDOWS), r["streak"]]
        )
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=4):
        for c in row:
            c.number_format = "0%"
    daily = wb.create_sheet("Daily")
    names = [h["Name"] for h in habits]
    daily.append(["Date", *names])
    fills = {"1": PatternFill("solid", fgColor="C6EFCE"), "0": PatternFill("solid", fgColor="FFC7CE")}
    for i in range(days):
        d = end - timedelta(days=i)
        values = []
        for n in names:
            v = marks[n].get(d, "UNKNOWN")
            values.append(1 if v in loop.YES else 0 if v == "NO" else None)
        daily.append([d, *values])
        for c in daily[daily.max_row][1:]:
            if c.value is not None:
                c.fill = fills[str(c.value)]
    for sheet in (ws, daily):
        for c in sheet[1]:
            c.font = Font(bold=True)
        sheet.column_dimensions["A"].width = 24
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _spark(weekly: list[float | None]) -> str:
    bars = []
    for i, r in enumerate(weekly):
        h = 2 + 26 * (r or 0)
        bars.append(f'<rect x="{i * 9}" y="{30 - h:.1f}" width="7" height="{h:.1f}" class="s {light(r)}"/>')
    return f'<svg class="spark" viewBox="0 0 {9 * len(weekly)} 30" aria-label="weekly completion">{"".join(bars)}</svg>'


def _heat(marks: dict, end: date, weeks: int = 13) -> str:
    start = end - timedelta(days=7 * weeks - 1)
    cells = []
    for i in range(7 * weeks):
        d = start + timedelta(days=i)
        v = marks.get(d, "UNKNOWN")
        kind = "y" if v in loop.YES else "n" if v == "NO" else "u"
        cells.append(f'<i class="{kind}" title="{d.isoformat()}: {v}"></i>')
    return f'<div class="heat">{"".join(cells)}</div>'


CSS = """
.spark{width:117px;height:30px}.spark .ok{fill:var(--ok)}.spark .warn{fill:var(--warn)}.spark .bad{fill:var(--bad)}
.spark .s{fill-opacity:.85}.heat{display:grid;grid-template-rows:repeat(7,9px);grid-auto-flow:column;gap:2px}
.heat i{width:9px;height:9px;border-radius:2px;background:var(--line)}.heat i.y{background:var(--ok)}
.heat i.n{background:var(--badbg);outline:1px solid var(--line)}
"""


def page(rows: list[dict], marks: dict, end: date, source: str, sheet: str) -> str:
    avg30 = [r["r30"] for r in rows if r["r30"] is not None]
    tiles = [
        (len(rows), "habits tracked"),
        (f"{sum(avg30) / len(avg30):.0%}", "average, last 30 days"),
        (max(r["streak"] for r in rows), "best current streak (days)"),
        (sum(1 for r in rows if light(r["r30"]) == "ok"), f"habits at or above {GOOD:.0%}"),
    ]
    tiles_html = "".join(
        f'<div class="panel tile"><div class="v">{v}</div><div class="l">{esc(lbl)}</div></div>' for v, lbl in tiles
    )
    trs = []
    for r in rows:
        cells = "".join(
            f'<td class="n"><span class="badge {light(r[f"r{w}"])}">{pct(r[f"r{w}"])}</span></td>' for w in WINDOWS
        )
        trs.append(
            f"<tr><td><b>{esc(r['name'])}</b></td>{cells}<td class=n>{r['streak']}</td>"
            f"<td>{_spark(r['weekly'])}</td><td>{_heat(marks[r['name']], end)}</td></tr>"
        )
    table = (
        '<div class="panel" style="overflow-x:auto"><table><tr><th>Habit</th><th class=n>14 d</th><th class=n>30 d</th>'
        "<th class=n>90 d</th><th class=n>Streak</th><th>Last 13 weeks</th><th>Day by day</th></tr>"
        + "".join(trs)
        + "</table></div>"
    )
    lead = (
        f"The phone app's export (<code>{esc(source)}</code>, the same CSV format Loop Habits writes) becomes a "
        f"spreadsheet (<code>{esc(sheet)}</code>) and this page. Green: done on at least {GOOD:.0%} of the days "
        f"recorded; amber: {FAIR:.0%} to {GOOD:.0%}; red: below. Last day in the export: {end.isoformat()}."
    )
    return shell("habits", "Habits", lead, f'<div class="grid g4">{tiles_html}</div><h2>Every habit</h2>{table}', CSS)
