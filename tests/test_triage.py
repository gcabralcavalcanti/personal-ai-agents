"""Job triage over the delta: code pre-filter, business-rule checks on the model's answer, idempotency, cap."""

import unittest

import _path  # noqa: F401
from fake_llm import make_llm

from career import triage as tr

PROFILE = {"candidate": "test", "graduation_windows": ["2027-12"], "geography": {"preferred": ["Rio de Janeiro"]}}
URL = "https://boards.greenhouse.io/examplebank"
STATE = {
    URL: {
        "company": "Example Bank (fictitious)",
        "area": "Banking",
        "items": [
            "Investment Banking Intern - Rio de Janeiro",
            "Senior Engineer - Remote",
            "Analista Pleno de Credito - Sao Paulo",
            "Summer Analyst - Recife",
        ],
    }
}


def verdict(decision="monitor", geography="preferred", grad="unknown"):
    return {
        "decision": decision,
        "graduation_fit": grad,
        "location": "x",
        "geography": geography,
        "prep_cost": "medium",
        "reason": "test",
    }


class Triage(unittest.TestCase):
    def test_code_discards_seniority_without_a_call(self):
        self.assertIsNotNone(tr.prefilter("Senior Engineer - Remote"))
        self.assertIsNotNone(tr.prefilter("Analista Pleno de Credito - Sao Paulo"))
        self.assertIsNotNone(tr.prefilter("Business Analyst II - Sao Paulo"))
        self.assertIsNone(tr.prefilter("Investment Banking Intern - Rio de Janeiro"))
        self.assertIsNone(tr.prefilter("Analista Junior de Marketing - Sao Paulo"))

    def test_business_rules_reject_apply_outside_geography(self):
        self.assertTrue(tr.check(verdict("apply", geography="outside")))
        self.assertTrue(tr.check(verdict("monitor", grad="does_not_fit")))
        self.assertEqual(tr.check(verdict("apply")), [])

    def test_bad_answer_is_retried_then_accepted(self):
        llm, _ = make_llm(
            [verdict("apply", geography="outside"), verdict("discard", geography="outside"), verdict("apply")]
        )
        store = {}
        counts = tr.triage(STATE, store, PROFILE, llm, "2026-03-01", max_calls=10)
        self.assertEqual(counts["by_code"], 2)
        self.assertEqual(counts["by_model"], 2)
        self.assertEqual(len(llm._client.messages.calls), 3)  # one retry for the rule violation
        decisions = sorted(r["decision"] for r in store.values())
        self.assertEqual(decisions, ["apply", "discard", "discard", "discard"])

    def test_second_run_is_free_and_gone_openings_close(self):
        llm, _ = make_llm([verdict(), verdict()])
        store = {}
        tr.triage(STATE, store, PROFILE, llm, "2026-03-01", max_calls=10)
        llm2, _ = make_llm([])
        counts = tr.triage(STATE, store, PROFILE, llm2, "2026-03-08", max_calls=10)
        self.assertEqual(counts["new"], 0)
        self.assertEqual(llm2._client.messages.calls, [])
        smaller = {URL: {**STATE[URL], "items": STATE[URL]["items"][:1]}}
        counts = tr.triage(smaller, store, PROFILE, llm2, "2026-03-15", max_calls=10)
        self.assertEqual(counts["closed"], 3)
        self.assertEqual(len(store), 4)  # closed, never deleted

    def test_call_cap_leaves_the_rest_for_next_run(self):
        llm, _ = make_llm([verdict(), verdict()])
        store = {}
        counts = tr.triage(STATE, store, PROFILE, llm, "2026-03-01", max_calls=1)
        self.assertEqual(counts["by_model"], 1)
        self.assertEqual(counts["left_for_next_run"], 1)
        self.assertEqual(len(store), 3)

    def test_report_lists_model_verdicts(self):
        llm, _ = make_llm([verdict("apply"), verdict("monitor")])
        store = {}
        counts = tr.triage(STATE, store, PROFILE, llm, "2026-03-01", max_calls=10)
        md = tr.render(store, counts, llm.summary(), "2026-03-01")
        self.assertIn("| apply | Example Bank", md)
        self.assertNotIn("Senior Engineer", md)  # code discards are counted, not listed


if __name__ == "__main__":
    unittest.main()
