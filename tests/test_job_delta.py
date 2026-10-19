"""Delta collection without network: a fake HTTP getter returns canned pages (fictitious companies)."""

import json
import os
import unittest

from _path import EXAMPLES

from career import job_delta as jd

GH = {
    "jobs": [
        {"title": "Investment Banking Intern", "location": {"name": "Sao Paulo"}},
        {"title": "Senior Engineer", "location": {"name": "Remote"}},
    ]
}
PAGE_V1 = "<html><body><h2>Open roles</h2><p>Strategy Internship 2027 | Finance</p></body></html>"
PAGE_V2 = PAGE_V1.replace("</p>", "</p><p>Trainee Program 2027 | Operations</p>")
SOURCES = jd.read_sources(os.path.join(EXAMPLES, "job_sources.csv"))


def fake_get(pages):
    def get(url, timeout=25):
        if "greenhouse" in url:
            return 200, json.dumps(GH)
        return 200, pages[url]

    return get


class JobDelta(unittest.TestCase):
    def test_blocked_sources_are_never_fetched(self):
        def boom(url, timeout=25):
            raise AssertionError("fetched a blocked source")

        self.assertEqual(jd.collect("https://www.linkedin.com/jobs/x", boom)["kind"], "blocked")

    def test_greenhouse_keeps_only_entry_level(self):
        res = jd.collect("https://boards.greenhouse.io/examplebank", fake_get({}))
        self.assertEqual(res["items"], ["Investment Banking Intern - Sao Paulo"])

    def test_first_run_then_idempotent_then_delta(self):
        pages = {u: PAGE_V1 for _, _, u in SOURCES if "greenhouse" not in u and "linkedin" not in u}
        s1, rows1 = jd.run(SOURCES, {}, "2026-03-01", fake_get(pages), pause=0)
        self.assertTrue(all(r[3].startswith(("first", "error")) for r in rows1), rows1)
        s2, rows2 = jd.run(SOURCES, s1, "2026-03-08", fake_get(pages), pause=0)
        self.assertTrue(all(r[3] == "unchanged" or r[3].startswith("error") for r in rows2), rows2)
        url = next(iter(pages))
        pages[url] = PAGE_V2
        _, rows3 = jd.run(SOURCES, s2, "2026-03-15", fake_get(pages), pause=0)
        changed = next(r for r in rows3 if r[2] == url)
        self.assertTrue(changed[3].startswith("CHANGED: +1"), changed)
        self.assertIn("Trainee Program 2027", changed[4][0])

    def test_error_is_a_result_not_a_crash(self):
        def down(url, timeout=25):
            raise TimeoutError("timed out")

        self.assertEqual(jd.collect("https://careers.example.com", down)["kind"], "error")


if __name__ == "__main__":
    unittest.main()
