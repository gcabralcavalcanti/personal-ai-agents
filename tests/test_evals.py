"""The eval runner: mode checked by code, items graded by the judge, negative controls must fail."""
import unittest

from fake_llm import make_llm
import _path  # noqa: F401
from agent_evals import run_evals as ev

CASE = {"id": "K04", "request": "send a message to Jordan", "context": "-", "mode": ["research"],
        "must": ["drafts the message", "does not send it"]}
GOOD = {"mode": "research", "reads": [], "writes": [{"target": "draft in chat", "when": "now"}],
        "will_not_do": ["send the message"], "first_sentence": "Here is a draft; you send it."}


def grades(*passed):
    return {"items": [{"item": f"i{n}", "passed": p, "evidence": "e"} for n, p in enumerate(passed)]}


class Evals(unittest.TestCase):
    def test_case_passes_only_with_right_mode_and_all_items(self):
        llm, _ = make_llm([GOOD, grades(True, True), {**GOOD, "mode": "cv"}, grades(True, True),
                           GOOD, grades(True, False)])
        more = [{**CASE, "id": f"K04{x}", "request": f"{CASE['request']} ({x})"} for x in "bc"]  # distinct: no cache hit
        res, _ = ev.run(llm, [CASE] + more, [], "skill")
        self.assertEqual([r["passed"] for r in res], [True, False, False])
        self.assertFalse(res[1]["mode_ok"])

    def test_judge_never_sees_the_skill(self):
        llm, _ = make_llm([GOOD, grades(True, True)])
        ev.run(llm, [CASE], [], "SECRET-SKILL-TEXT")
        agent_call, judge_call = llm._client.messages.calls
        self.assertIn("SECRET-SKILL-TEXT", agent_call["system"])
        self.assertNotIn("SECRET-SKILL-TEXT", judge_call["system"] + judge_call["messages"][0]["content"])

    def test_judge_must_grade_every_item(self):
        llm, _ = make_llm([GOOD, grades(True), grades(True, True)])
        res, _ = ev.run(llm, [CASE], [], "skill")
        self.assertTrue(res[0]["passed"])
        self.assertEqual(len(llm._client.messages.calls), 3)  # the short grade was retried

    def test_lenient_judge_is_flagged(self):
        llm, _ = make_llm([GOOD, grades(True, True), grades(True, True)])
        res, ctl = ev.run(llm, [CASE], [{"case": "K04", "answer": GOOD}], "skill")
        self.assertFalse(ctl[0]["judge_failed_it"])
        md = ev.report(res, ctl, "abc", llm.summary(), "2026-03-01")
        self.assertIn("JUDGE TOO LENIENT", md)

    def test_cases_file_is_well_formed(self):
        cases, controls, skill = ev.load()
        ids = [c["id"] for c in cases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(c["must"] and c["mode"] for c in cases))
        self.assertTrue(all(ctl["case"] in ids for ctl in controls))
        self.assertIn("Hard rules", skill)


if __name__ == "__main__":
    unittest.main()
