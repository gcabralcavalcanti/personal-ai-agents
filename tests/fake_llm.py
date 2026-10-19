"""A stand-in for the Anthropic client: canned answers, no network, no key, no cost."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import _path  # noqa: F401
from llm.client import LLM


class FakeMessages:
    def __init__(self, answers):
        self.answers = list(answers)   # str (JSON text), dict, or an Exception to raise
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        nxt = self.answers.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        if callable(nxt):
            nxt = nxt(kw)
        text = nxt if isinstance(nxt, str) else json.dumps(nxt)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=10))


def make_llm(answers, max_calls=10, tmp=None):
    """A live-mode LLM whose API client is FakeMessages. Returns (llm, tmpdir)."""
    tmp = Path(tmp or tempfile.mkdtemp())
    llm = LLM(mode="demo", max_calls=max_calls, recordings=tmp / "rec", log_dir=tmp / "logs", sleep=lambda s: None)
    llm.mode = "live"
    llm._client = SimpleNamespace(messages=FakeMessages(answers))
    return llm, tmp
