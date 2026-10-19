"""Planner -> validator -> writes, the trace, and the end-to-end demo (replayed answers, no key, no network)."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _path import EXAMPLES
from fake_llm import make_llm

from todoist_gate import planner
from tracing import view
from tracing.trace import Trace

BOARD = json.loads(Path(EXAMPLES, "demo_board.json").read_text(encoding="utf-8"))
DAY11 = [
    {"content": "Deep work: thesis chapter 2", "start": "09:00", "duration_min": 120, "timebox": False},
    {"content": "Download dataset", "start": "13:00", "duration_min": 20, "timebox": False},
    {"content": "Run regression", "start": "14:00", "duration_min": 60, "timebox": False},
    {"content": "Gym", "start": "18:00", "duration_min": 60, "timebox": False},
]
DAY12 = [
    {"content": "Study group prep", "start": "09:00", "duration_min": 60, "timebox": False},
    {"content": "Weekly report", "start": "10:00", "duration_min": 90, "timebox": False},
    {"content": "Send slides to study group", "start": "16:00", "duration_min": 30, "timebox": False},
]
GOOD = {
    "days": [{"date": "2026-03-11", "items": DAY11}, {"date": "2026-03-12", "items": DAY12}],
    "reschedule_overdue": [{"content": "Pay library fine", "date": "2026-03-10"}],
    "request_fulfilled": True,
    "open_question": "",
    "summary": "ok",
}


class Planner(unittest.TestCase):
    def test_good_batch_closes_and_becomes_exact_tool_calls(self):
        res, _ = planner.validate(BOARD, GOOD)
        self.assertTrue(res["ok"], res)
        calls = {c["tool_name"].split("__")[-1]: c["tool_input"]["tasks"] for c in planner.writes(BOARD, GOOD)}
        self.assertEqual({t["id"] for t in calls["reschedule-tasks"]}, {"t2", "t7"})
        self.assertEqual(calls["add-tasks"][0]["dueString"], "Mar 11 at 14:00")

    def test_only_the_requested_day_is_blocked(self):
        naive = {**GOOD, "days": [{"date": "2026-03-12", "items": DAY12}], "reschedule_overdue": []}
        res, text = planner.validate(BOARD, naive)
        self.assertFalse(res["ok"])
        self.assertIn("COVERAGE", text)  # the report's origin day is missing
        self.assertIn("PAST_DIRTY", text)

    def test_a_rewritten_day_cannot_lose_a_task(self):
        lost = {**GOOD, "days": [{"date": "2026-03-11", "items": DAY11[:2]}, GOOD["days"][1]]}
        _res, text = planner.validate(BOARD, lost)
        self.assertIn('LOST_TASK: "Gym"', text)

    def test_unfulfilled_request_goes_to_the_human(self):
        res, text = planner.validate(BOARD, {**GOOD, "request_fulfilled": False, "open_question": "which day?"})
        self.assertFalse(res["ok"])
        self.assertIn("UNFULFILLED", text)

    def test_board_view_scopes(self):
        self.assertNotIn("Gym", planner.board_view(BOARD, "day"))
        full = planner.board_view(BOARD, "full")
        self.assertIn("Gym", full)
        self.assertIn("Pay library fine", full)
        self.assertIn("(Wed)", full)


class Tracing(unittest.TestCase):
    def test_steps_carry_status_duration_tokens_and_cost(self):
        llm, tmp = make_llm(['{"x": 1}'])
        tr = Trace("t", llm, root=tmp)
        with tr.step("model", round=1):
            llm.ask("t", "s", "p", {"type": "object"})
        with tr.step("rule") as s:
            s["status"] = "blocked"
        total = tr.close()
        rows = view.load(tr.path)
        self.assertEqual([r["stage"] for r in rows], ["model", "rule", "run"])
        self.assertEqual(rows[0]["api_calls"], 1)
        self.assertEqual(rows[0]["input_tokens"], 100)
        self.assertEqual(rows[1]["status"], "blocked")
        self.assertGreater(total["cost_usd"], 0)
        self.assertIn("model round=1", view.table(rows))
        self.assertIn("<table>", view.page(rows, "x"))

    def test_error_is_recorded_and_raised(self):
        tr = Trace("t", None, root=tempfile.mkdtemp())
        with self.assertRaises(ValueError), tr.step("boom"):
            raise ValueError("bad")
        self.assertEqual(view.load(tr.path)[0]["status"], "error")


class Demo(unittest.TestCase):
    def test_demo_runs_end_to_end_from_recordings(self):
        import demo

        out = io.StringIO()
        with redirect_stdout(out):
            code = demo.main(["--yes"])
        text = out.getvalue()
        self.assertEqual(code, 0, text[-2000:])
        self.assertIn("BLOCKED (gate)", text)
        self.assertIn("BATCH OPEN", text)
        self.assertIn("BATCH CLOSED", text)
        self.assertIn("reschedule-tasks: exit 0, add-tasks: exit 0", text)
        self.assertIn("0 API call(s) now", text)


if __name__ == "__main__":
    unittest.main()
