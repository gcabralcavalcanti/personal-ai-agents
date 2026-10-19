"""Golden cases for the batch validator: each one reproduces a class of real planning error (fictitious data)."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

from _path import EXAMPLES, SRC
from todoist_gate.check_batch import check_batch

with open(os.path.join(EXAMPLES, "batch_ok.json"), encoding="utf-8") as _f:
    OK = json.load(_f)
with open(os.path.join(EXAMPLES, "batch_blocked.json"), encoding="utf-8") as _f:
    BAD = json.load(_f)
CLI = os.path.join(SRC, "todoist_gate", "check_batch.py")


def codes(res):
    found = [b.split(":")[0] for b in res["blockers"]]
    found += [e.split(":")[0] for p in res["days"] for e in p["errors"]]
    return set(found)


class CheckBatch(unittest.TestCase):
    def test_clean_batch_closes(self):
        self.assertTrue(check_batch(OK)["ok"])

    def test_blocked_example_reports_every_class(self):
        res = check_batch(BAD)
        self.assertFalse(res["ok"])
        self.assertTrue({"OVERLAP", "NIGHT", "PAST_DIRTY", "COVERAGE", "DEP_CROSSDAY"} <= codes(res), codes(res))
        self.assertTrue(res["decisions"])

    def test_one_broken_day_blocks_whole_batch(self):
        b = copy.deepcopy(OK)
        b["days"][1]["items"].append({"content": "Call advisor", "start": "10:30", "duration_min": 30})
        res = check_batch(b)
        self.assertFalse(res["ok"])
        self.assertTrue(res["days"][0]["ok"])

    def test_pin_drift(self):
        b = copy.deepcopy(OK)
        b["days"].append({"date": "2026-03-13", "items": [b["days"][1]["items"].pop()]})
        self.assertIn("PIN_DRIFT", codes(check_batch(b)))

    def test_item_inside_timebox_is_not_overlap(self):
        self.assertNotIn("OVERLAP", codes(check_batch(OK)))

    def test_past_start_today(self):
        b = copy.deepcopy(OK)
        b["days"].insert(0, {"date": "2026-03-10",
                             "items": [{"content": "Review notes", "start": "07:00", "duration_min": 30}]})
        self.assertIn("PAST", codes(check_batch(b)))

    def test_day_in_past(self):
        b = copy.deepcopy(OK)
        b["days"][0]["date"] = "2026-03-09"
        self.assertIn("DAY_IN_PAST", codes(check_batch(b)))

    def test_budget_becomes_a_decision_not_silent_cramming(self):
        b = copy.deepcopy(OK)
        b["days"][1]["budget_hours"] = 1
        res = check_batch(b)
        self.assertFalse(res["ok"])
        self.assertTrue(any("BUDGET" in x for x in res["decisions"]))

    def test_shape_error_stops_before_rules(self):
        res = check_batch({"days": []})
        self.assertFalse(res["ok"])
        self.assertTrue(all(b.startswith("SHAPE") for b in res["blockers"]))

    def test_cli_closed_batch_opens_gate(self):
        d = tempfile.mkdtemp()
        p = subprocess.run([sys.executable, CLI, os.path.join(EXAMPLES, "batch_ok.json")],
                           capture_output=True, text=True, env=dict(os.environ, GATE_FLAGS_DIR=d))
        self.assertEqual(p.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(d, "GATE-OK")))

    def test_cli_open_batch_keeps_gate_closed(self):
        d = tempfile.mkdtemp()
        p = subprocess.run([sys.executable, CLI, os.path.join(EXAMPLES, "batch_blocked.json")],
                           capture_output=True, text=True, env=dict(os.environ, GATE_FLAGS_DIR=d))
        self.assertEqual(p.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(d, "GATE-OK")))


if __name__ == "__main__":
    unittest.main()
