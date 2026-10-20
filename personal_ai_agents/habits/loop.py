"""Read a Loop Habits Tracker CSV export (the ZIP the phone app writes) and compute completion rates.

The export has `Habits.csv` (one row per habit) and a root `Checkmarks.csv` in wide format: one row per day, newest
first, one column per habit, values YES_MANUAL, YES_AUTO, NO, SKIP or UNKNOWN. This module also writes a fictitious
export in the same format, so the demo runs on a file the real pipeline would accept.
"""

from __future__ import annotations

import csv
import io
import random
import zipfile
from datetime import date, timedelta
from pathlib import Path

YES = {"YES_MANUAL", "YES_AUTO"}
# Fictitious habits: name, question, how often it was done at the start and at the end of the period.
FICTITIOUS = [
    ("Plan tomorrow", "Did you plan tomorrow?", 0.80, 0.85),
    ("Deep work block", "Did you do a 90-minute focus block?", 0.45, 0.70),
    ("Read 20 pages", "Did you read 20 pages?", 0.55, 0.75),
    ("Language practice", "Did you practise the language?", 0.50, 0.35),
    ("Walk 30 minutes", "Did you walk 30 minutes?", 0.60, 0.60),
    ("No screens after 11 pm", "Did you stay off screens after 11 pm?", 0.25, 0.50),
]
COLORS = ["#1976D2", "#388E3C", "#F57C00", "#8E24AA", "#00897B", "#D32F2F"]


def _csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def write_fictitious_export(path: Path, end: date, days: int = 120, seed: int = 7) -> Path:
    rng = random.Random(seed)
    dates = [end - timedelta(days=i) for i in range(days)]  # newest first, as the app writes it
    marks = {}
    for name, _, start, finish in FICTITIOUS:
        for i, d in enumerate(dates):
            p = finish + (start - finish) * i / (days - 1)  # i = 0 is the newest day
            r = rng.random()
            marks[(name, d)] = "UNKNOWN" if r > 0.97 else ("YES_MANUAL" if rng.random() < p else "NO")
    habits = [["Position", "Name", "Type", "Question", "Description", "FrequencyNumerator", "FrequencyDenominator",
               "Color", "Unit", "Target Type", "Target Value", "Archived?"]]  # fmt: skip
    for i, (name, question, _, _) in enumerate(FICTITIOUS, 1):
        habits.append([f"{i:03d}", name, "YES_NO", question, "", 1, 1, COLORS[i - 1], "", "", "", "false"])
    root = [["Date"] + [h[0] for h in FICTITIOUS] + [""]]
    root += [[d.isoformat()] + [marks[(h[0], d)] for h in FICTITIOUS] + [""] for d in dates]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Habits.csv", _csv(habits))
        z.writestr("Checkmarks.csv", _csv(root))
        for i, (name, *_rest) in enumerate(FICTITIOUS, 1):
            rows = [["Date", "Value", "Notes"]] + [[d.isoformat(), marks[(name, d)], ""] for d in dates]
            z.writestr(f"{i:03d} {name}/Checkmarks.csv", _csv(rows))
    return path


def read_export(path: Path) -> tuple[list[dict], dict[str, dict[date, str]]]:
    """(habits, marks): habits from Habits.csv (archived ones dropped), marks[name][day] = value."""
    with zipfile.ZipFile(path) as z:
        habits = list(csv.DictReader(io.StringIO(z.read("Habits.csv").decode("utf-8"))))
        rows = list(csv.reader(io.StringIO(z.read("Checkmarks.csv").decode("utf-8"))))
    habits = [h for h in habits if h.get("Archived?", "false") != "true"]
    names = rows[0][1:]
    marks: dict[str, dict[date, str]] = {h["Name"]: {} for h in habits}
    for row in rows[1:]:
        day = date.fromisoformat(row[0])
        for name, value in zip(names, row[1:], strict=False):
            if name in marks:
                marks[name][day] = value
    return habits, marks


def rate(marks: dict[date, str], end: date, days: int) -> float | None:
    """Share of days done among days recorded (YES vs NO); SKIP and UNKNOWN do not count."""
    window = [marks.get(end - timedelta(days=i), "UNKNOWN") for i in range(days)]
    done, missed = sum(v in YES for v in window), sum(v == "NO" for v in window)
    return done / (done + missed) if done + missed else None


def streak(marks: dict[date, str], end: date) -> int:
    n, d = 0, end
    while marks.get(d) in YES or marks.get(d) == "SKIP":
        n += marks.get(d) in YES
        d -= timedelta(days=1)
    return n


def weekly(marks: dict[date, str], end: date, weeks: int = 13) -> list[float | None]:
    """Completion rate per week, oldest first."""
    return [rate(marks, end - timedelta(days=7 * w), 7) for w in reversed(range(weeks))]
