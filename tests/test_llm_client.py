"""The API wrapper: schema, semantic check, retries, backoff, cache, call cap, demo mode, log. No network."""

import json
import unittest

import _path  # noqa: F401
import anthropic
import httpx2
from fake_llm import make_llm

from llm import client as client_mod
from llm.client import LLM, BudgetExceeded, NoRecording

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["x"], "properties": {"x": {"type": "number"}}}


def connection_error():
    return anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


class LLMClient(unittest.TestCase):
    def test_answer_is_recorded_and_never_paid_twice(self):
        llm, _ = make_llm(['{"x": 1}'])
        self.assertEqual(llm.ask("t", "sys", "p", SCHEMA), {"x": 1})
        self.assertEqual(llm.ask("t", "sys", "p", SCHEMA), {"x": 1})
        self.assertEqual(len(llm._client.messages.calls), 1)
        self.assertEqual(llm.cache_hits, 1)

    def test_request_carries_schema_and_cost_controls(self):
        llm, _ = make_llm(['{"x": 1}'])
        llm.ask("t", "sys", "p", SCHEMA)
        kw = llm._client.messages.calls[0]
        self.assertEqual(kw["model"], "claude-haiku-5-5")
        self.assertLessEqual(kw["max_tokens"], 1000)
        self.assertEqual(kw["output_config"]["format"]["schema"], SCHEMA)
        self.assertEqual(kw["output_config"]["effort"], "low")

    def test_schema_failure_retries_with_the_checker_feedback(self):
        llm, _ = make_llm(['{"x": "one"}', '{"x": 1}'])
        self.assertEqual(llm.ask("t", "sys", "p", SCHEMA), {"x": 1})
        self.assertIn("rejected by the checker", llm._client.messages.calls[1]["messages"][0]["content"])

    def test_semantic_check_failure_raises_and_is_not_recorded(self):
        llm, tmp = make_llm(['{"x": 1}', '{"x": 1}'])
        with self.assertRaises(ValueError):
            llm.ask("t", "sys", "p", SCHEMA, check=lambda a: [] if a["x"] == 2 else ["x must be 2"])
        self.assertEqual(list((tmp / "rec").glob("*.json")), [])

    def test_backoff_on_connection_errors_then_success(self):
        llm, _ = make_llm([connection_error(), connection_error(), '{"x": 5}'])
        delays = []
        llm.sleep = delays.append
        self.assertEqual(llm.ask("t", "sys", "p", SCHEMA), {"x": 5})
        self.assertEqual(len(delays), 2)
        self.assertGreater(delays[1], delays[0])  # exponential

    def test_backoff_gives_up_after_the_limit(self):
        llm, _ = make_llm([connection_error()] * 10)
        with self.assertRaises(anthropic.APIConnectionError):
            llm.ask("t", "sys", "p", SCHEMA)

    def test_call_cap(self):
        llm, _ = make_llm(['{"x": 1}', '{"x": 2}'], max_calls=1)
        llm.ask("a", "sys", "p1", SCHEMA)
        with self.assertRaises(BudgetExceeded):
            llm.ask("b", "sys", "p2", SCHEMA)

    def test_demo_mode_replays_or_stops(self):
        live, tmp = make_llm(['{"x": 3}'])
        live.ask("t", "sys", "p", SCHEMA)
        orig, client_mod.load_key = client_mod.load_key, lambda *a: None
        try:
            demo = LLM(mode="auto", recordings=tmp / "rec", log_dir=tmp / "logs")
        finally:
            client_mod.load_key = orig
        self.assertEqual(demo.mode, "demo")
        self.assertEqual(demo.ask("t", "sys", "p", SCHEMA), {"x": 3})
        with self.assertRaises(NoRecording):
            demo.ask("t", "sys", "another prompt", SCHEMA)

    def test_log_is_one_json_line_per_call_and_never_holds_the_key(self):
        llm, _ = make_llm(['{"x": 1}'])
        llm.ask("t", "sys", "p", SCHEMA)
        lines = [json.loads(line) for line in llm.log_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(lines[0]["source"], "api")
        self.assertEqual(lines[0]["input_tokens"], 100)
        self.assertNotIn("sk-ant", llm.log_path.read_text(encoding="utf-8"))
        self.assertAlmostEqual(llm.cost_usd(), (100 * 0.10 + 10 * 0.50) / 1e6)


if __name__ == "__main__":
    unittest.main()
