"""Runs the hook exactly as Claude Code does: JSON on stdin, exit 2 = blocked. Flags in a temp dir."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from _path import SRC

HOOK = os.path.join(SRC, "todoist_gate", "gate_hook.py")
MCP = "mcp__todoist__"


def run(tool, inp, flags=(), age_s=0):
    d = tempfile.mkdtemp()
    for f in flags:
        p = os.path.join(d, f)
        open(p, "w").close()
        if age_s:
            t0 = time.time() - age_s
            os.utime(p, (t0, t0))
    env = dict(os.environ, GATE_FLAGS_DIR=d)
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": MCP + tool, "tool_input": inp}),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stderr


TIMED = {"tasks": [{"content": "Weekly report", "dueString": "Mar 12 at 10:00"}]}


class GateHook(unittest.TestCase):
    def test_r2_update_with_due_blocks(self):
        code, err = run("update-tasks", {"tasks": [{"id": "x", "dueString": "every day at 9:15"}]})
        self.assertEqual(code, 2)
        self.assertIn("R2", err)

    def test_r2_with_flag_passes(self):
        self.assertEqual(run("update-tasks", {"tasks": [{"id": "x", "dueString": "tomorrow"}]}, ["I7-OK"])[0], 0)

    def test_r2_expired_flag_blocks(self):
        code, err = run("update-tasks", {"tasks": [{"id": "x", "dueString": "every thu"}]}, ["I7-OK"], age_s=16 * 60)
        self.assertEqual(code, 2)
        self.assertIn("older than 15 minutes", err)

    def test_update_without_due_passes(self):
        self.assertEqual(run("update-tasks", {"tasks": [{"id": "x", "content": "rename"}]})[0], 0)

    def test_timed_add_without_checked_batch_blocks(self):
        self.assertEqual(run("add-tasks", TIMED)[0], 2)

    def test_time_formats_detected(self):
        for due in ("tomorrow 10h", "Mar 12 at 9:00", "friday 3pm"):
            self.assertEqual(run("add-tasks", {"tasks": [{"content": "x", "dueString": due}]})[0], 2, due)

    def test_untimed_add_passes(self):
        self.assertEqual(run("add-tasks", {"tasks": [{"content": "Buy notebook", "dueString": "Mar 12"}]})[0], 0)

    def test_mixed_batch_blocks(self):
        inp = {"tasks": [{"content": "a", "dueString": "Mar 12"}, {"content": "b", "dueString": "Mar 13 at 9:00"}]}
        self.assertEqual(run("add-tasks", inp)[0], 2)

    def test_gate_flag_passes(self):
        self.assertEqual(run("add-tasks", TIMED, ["GATE-OK"])[0], 0)
        self.assertEqual(run("reschedule-tasks", {"tasks": [{"id": "x"}]}, ["GATE-OK"])[0], 0)

    def test_expired_flag_blocks(self):
        code, err = run("add-tasks", TIMED, ["GATE-OK"], age_s=16 * 60)
        self.assertEqual(code, 2)
        self.assertIn("older than 15 minutes", err)

    def test_r36_delete_needs_flag(self):
        self.assertEqual(run("delete-object", {"type": "task", "id": "x"})[0], 2)
        self.assertEqual(run("delete-object", {"type": "task", "id": "x"}, ["DELETE-OK"])[0], 0)

    def test_reads_never_blocked(self):
        self.assertEqual(run("find-tasks", {"searchText": "report"})[0], 0)

    def test_garbage_stdin_never_blocks(self):
        p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
