"""Level-triggered queue: findings open when a check fails and close by themselves when it passes."""
import os
import shutil
import tempfile
import unittest
from datetime import date

from _path import EXAMPLES
from optimizer import queue as q


class Queue(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(tempfile.mkdtemp(), "s")
        shutil.copytree(os.path.join(EXAMPLES, "sample_system"), self.root)

    def test_sample_findings(self):
        found = {(i["check"], i["target"]) for i in q.check_structure(self.root)}
        self.assertIn(("manifest", "agents/12-agent-reports"), found)
        self.assertIn(("manifest", "agents/11-agent-notes/CLAUDE.md"), found)
        self.assertFalse(any("10-agent-planner" in t for _, t in found))

    def test_fixed_item_closes_by_itself_and_keeps_since(self):
        state, new, _ = q.reconcile(q.check_structure(self.root), {}, date(2026, 3, 1))
        self.assertEqual(len(new), 2)
        shutil.copy(os.path.join(self.root, "agents", "10-agent-planner", "CLAUDE.md"),
                    os.path.join(self.root, "agents", "11-agent-notes", "CLAUDE.md"))
        state2, new2, closed2 = q.reconcile(q.check_structure(self.root), state, date(2026, 3, 8))
        self.assertEqual(new2, [])
        self.assertEqual(len(closed2), 1)
        self.assertEqual(list(state2.values())[0]["since"], "2026-03-01")

    def test_size_limit(self):
        p = os.path.join(self.root, "agents", "10-agent-planner", "CLAUDE.md")
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" * 250)
        self.assertIn("size", {i["check"] for i in q.check_structure(self.root)})


if __name__ == "__main__":
    unittest.main()
