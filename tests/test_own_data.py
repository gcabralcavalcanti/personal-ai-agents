"""Your own data: the habit app's backup, a Todoist read into a board, and the flashcards x calendar week."""

import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from _path import DATA, ROOT

from personal_ai_agents.habits import loop
from personal_ai_agents.study import anki_forecast, plan
from personal_ai_agents.todoist_gate import check_batch, todoist_export


def ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def tiny_backup(path: Path) -> Path:
    """The two tables of the app's backup the reader uses, with one yes/no, one measurable and one archived habit."""
    con = sqlite3.connect(path)
    con.execute(
        "create table Habits (id integer, name text, type integer, archived integer, question text, "
        "target_type integer, target_value real, position integer)"
    )
    con.execute("create table Repetitions (habit integer, timestamp integer, value integer)")
    con.executemany(
        "insert into Habits values (?,?,?,?,?,?,?,?)",
        [
            (1, "Read", 0, 0, "Did you read?", 0, 0, 0),
            (2, "Steps", 1, 0, "How many steps?", 0, 8000, 1),
            (3, "Old habit", 0, 1, "", 0, 0, 2),
        ],
    )
    d1, d2, d3 = date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)
    con.executemany(
        "insert into Repetitions values (?,?,?)",
        [
            (1, ms(d1), 2),
            (1, ms(d2), 1),
            (1, ms(d3), 0),
            (2, ms(d1), 9500 * 1000),
            (2, ms(d2), 3000 * 1000),
            (2, ms(d3), 3),
            (3, ms(d1), 2),
        ],
    )
    con.commit()
    con.close()
    return path


class HabitBackup(unittest.TestCase):
    def test_backup_reads_like_the_export(self):
        path = tiny_backup(Path(tempfile.mkdtemp()) / "Loop Habits Backup.db")
        habits, marks = loop.read_any(path)
        self.assertEqual([h["Name"] for h in habits], ["Read", "Steps"])  # archived habit dropped
        self.assertEqual(
            marks["Read"],
            {date(2026, 3, 1): "YES_MANUAL", date(2026, 3, 2): "YES_AUTO", date(2026, 3, 3): "NO"},
        )
        # measurable habit: compared with its target (8000 steps)
        self.assertEqual(
            marks["Steps"], {date(2026, 3, 1): "YES_MANUAL", date(2026, 3, 2): "NO", date(2026, 3, 3): "SKIP"}
        )
        self.assertEqual(loop.last_day(marks), date(2026, 3, 3))

    def test_demo_takes_the_backup(self):
        import demo

        path = tiny_backup(Path(tempfile.mkdtemp()) / "backup.db")
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(demo.main(["habits", "--input", str(path), "--no-open"]), 0)
        self.assertIn("2 habits", out.getvalue())
        self.assertIn("backup.db", (Path(ROOT) / "output" / "habits.html").read_text(encoding="utf-8"))


class TodoistBoard(unittest.TestCase):
    def test_pages_are_followed_until_no_cursor(self):
        pages = [{"results": [{"id": "1"}], "next_cursor": "abc"}, {"results": [{"id": "2"}], "next_cursor": None}]
        urls = []

        def get(url, tok):
            urls.append(url)
            return pages[len(urls) - 1]

        self.assertEqual([t["id"] for t in todoist_export.fetch("today", "tok", get)], ["1", "2"])
        self.assertIn("cursor=abc", urls[1])

    def test_tasks_become_a_board_the_checker_accepts(self):
        tasks = [
            {"id": "a", "content": "Report", "due": {"date": "2026-03-11T09:00:00"}, "duration": {"amount": 90}},
            {"id": "b", "content": "Gym", "due": {"date": "2026-03-11T18:00:00"}},
            {"id": "c", "content": "Buy stamps", "due": {"date": "2026-03-11"}},  # no time: not on the calendar
            {"id": "d", "content": "Old bill", "due": {"date": "2026-03-08"}},
            {"id": "e", "content": "Someday"},
        ]
        board = todoist_export.to_board(tasks, date(2026, 3, 10), "08:00")
        self.assertEqual(
            board["days"]["2026-03-11"],
            [
                {"id": "a", "content": "Report", "start": "09:00", "duration_min": 90},
                {"id": "b", "content": "Gym", "start": "18:00", "duration_min": 30},
            ],
        )
        self.assertEqual([o["id"] for o in board["overdue"]], ["d"])
        demo_board = json.loads((Path(DATA) / "demo_board.json").read_text(encoding="utf-8"))
        self.assertTrue(set(demo_board) - {"_comment"} <= set(board))  # same keys the demo reads

    def test_an_empty_token_means_no_token(self):
        with mock.patch.dict(os.environ, {"TODOIST_API_TOKEN": ""}):
            self.assertIsNone(todoist_export.token())
            with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(todoist_export.main([]), 2)


class AnkiForecast(unittest.TestCase):
    def test_forecast_uses_only_reading_actions(self):
        sent = []

        def post(action, params):
            sent.append(action)
            if action == "deckNames":
                return ["Statistics", "Default"]
            if action == "getDeckConfig":
                return {"new": {"perDay": 20}}
            query = params["query"]
            if "is:new" in query:
                return list(range(12))
            return list(range(9 if "is:due" in query else int(query[-1])))

        f = anki_forecast.forecast(["Statistics"], days=4, post=post)
        self.assertEqual(f, [{"deck": "Statistics", "due": [9, 1, 2, 3], "new_per_day": 12}])
        self.assertTrue(set(sent) <= anki_forecast.READ_ONLY)
        with self.assertRaises(SystemExit):
            anki_forecast.forecast(["Missing"], post=post)


class StudyBlocks(unittest.TestCase):
    def setUp(self):
        self.week = json.loads((Path(DATA) / "study_week.json").read_text(encoding="utf-8"))

    def test_contract_check(self):
        a = plan.audit(self.week)
        self.assertEqual(a["orphans"], ["Biology", "Business::Metrics", "History"])
        self.assertEqual(a["missing_deck"], ["Cards: Economics"])
        self.assertEqual(a["no_deck_line"], ["Review cards"])

    def test_load_comes_from_the_forecast(self):
        f = next(f for f in self.week["forecast"] if f["deck"] == "History")
        expected = -(-(f["due"][0] * 8 + f["new_per_day"] * 25) // 60)
        self.assertEqual(plan.load(self.week)["History"][0], expected)

    def test_naive_plan_is_blocked_and_fitted_plan_passes_the_gate(self):
        r = plan.run(self.week, lambda: True)
        naive, fitted = r["rounds"]
        self.assertFalse(naive["ok"])
        self.assertIn("OVERLAP", naive["report"])
        self.assertTrue(fitted["ok"])
        res = check_batch.check_batch(plan.batch(self.week, fitted["blocks"]))
        self.assertTrue(res["ok"])
        tasks = r["calls"][0]["tool_input"]["tasks"]
        self.assertTrue(all(t["description"].startswith("deck: ") for t in tasks))
        self.assertEqual(
            {t["description"][6:] for t in tasks}, {"Business::Metrics", "History"}
        )  # Biology: too few cards
        self.assertEqual([code for code, _ in r["hook"]], [0])

    def test_not_approved_means_no_call_reaches_the_gate(self):
        r = plan.run(self.week, lambda: False)
        self.assertFalse(r["approved"])
        self.assertEqual(r["hook"], [])

    def test_shortfall_is_reported_not_changed(self):
        short = plan.shortfalls(self.week)
        self.assertIn("Cards: Statistics", {s["block"] for s in short})
        block = next(b for b in self.week["fixed"] if b["content"] == "Cards: Statistics")
        self.assertEqual(block["duration_min"], 20)

    def test_demo_writes_the_page(self):
        import demo

        with redirect_stdout(io.StringIO()):
            self.assertEqual(demo.main(["study", "--yes", "--no-open"]), 0)
        html = (Path(ROOT) / "output" / "study.html").read_text(encoding="utf-8")
        self.assertIn("batch closed", html)
        self.assertIn("deck: History", html)


if __name__ == "__main__":
    unittest.main()
