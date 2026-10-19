"""Small wrapper around the Claude Messages API used by every script here.

Answers must match a JSON Schema (sent with the request, checked again locally) and an optional rule check;
a failing answer is retried once with the complaints. Network errors get exponential backoff. Accepted answers
are recorded, so an identical request is never paid twice and runs replay without a key (demo mode).
One JSON log line per call. The API key is read from the environment or .env and never logged.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from . import config


class BudgetExceeded(RuntimeError):
    """The run reached its call cap. Nothing else is sent."""


class NoRecording(RuntimeError):
    """Demo mode and this exact request was never recorded."""


def load_key(root: Path = config.ROOT) -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ANTHROPIC_API_KEY" and value.strip():
                return value.strip().strip('"')
    if os.name == "nt":  # set with `setx` after this terminal was opened
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                return winreg.QueryValueEx(k, "ANTHROPIC_API_KEY")[0] or None
        except OSError:
            return None
    return None


def load_schema(name: str) -> dict:
    return json.loads((config.SCHEMAS / f"{name}.json").read_text(encoding="utf-8"))


def request_hash(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]


class LLM:
    """mode: 'auto' (live if a key exists, else demo), 'live' or 'demo'."""

    def __init__(
        self,
        mode: str = "auto",
        max_calls: int = config.MAX_CALLS_PER_RUN,
        recordings: Path = config.RECORDINGS,
        log_dir: Path = config.LOGS,
        sleep: Callable[[float], None] = time.sleep,
    ):
        key = None if mode == "demo" else load_key()
        if mode == "live" and not key:
            raise RuntimeError("Live mode needs ANTHROPIC_API_KEY (environment or .env).")
        self.mode = "live" if key else "demo"
        self.max_calls = max_calls
        self.recordings = Path(recordings)
        self.recordings.mkdir(parents=True, exist_ok=True)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self.log_path = Path(log_dir) / f"run-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        self.sleep = sleep
        self.calls = self.cache_hits = self.tokens_in = self.tokens_out = 0
        self.replayed_in = self.replayed_out = 0  # tokens the replayed answers cost when they were recorded
        self._client = None
        if key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=key, timeout=config.TIMEOUT_S, max_retries=0)

    # ------------------------------------------------------------------ public
    def ask(
        self,
        task: str,
        system: str,
        prompt: str,
        schema: dict,
        check: Callable[[dict], list[str]] | None = None,
        max_tokens: int = config.MAX_TOKENS,
        effort: str = "low",
    ) -> dict:
        """Return a dict that matches `schema` and passes `check` (a list of problems; empty = ok).
        effort: 'low' (default, thinking off) or 'medium'/'high' (adaptive thinking, for planning steps)."""
        req = {"model": config.MODEL, "system": system, "prompt": prompt, "schema": schema, "max_tokens": max_tokens}
        if effort != "low":
            req["effort"] = effort
        key = request_hash(req)
        path = self.recordings / f"{task}-{key}.json"
        if path.exists():
            rec = json.loads(path.read_text(encoding="utf-8"))
            self.cache_hits += 1
            used = rec.get("usage", {})
            self.replayed_in += used.get("input_tokens", 0)
            self.replayed_out += used.get("output_tokens", 0)
            self._log(task, key, "recording")
            return rec["answer"]
        if self.mode == "demo":
            raise NoRecording(f"No recorded answer for {task} ({key}); run once with an API key.")

        problems: list[str] = []
        user = prompt
        spent = [0, 0]
        for attempt in range(config.SCHEMA_RETRIES + 1):
            t0 = time.monotonic()
            answer, usage = self._call(system, user, schema, max_tokens, effort)
            spent = [spent[0] + usage[0], spent[1] + usage[1]]
            problems = self.problems(answer, schema, check)
            self._log(task, key, "api", usage, problems, attempt, int((time.monotonic() - t0) * 1000))
            if not problems:
                path.write_text(
                    json.dumps(
                        {
                            "task": task,
                            "model": config.MODEL,
                            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "request": {"system": system, "prompt": prompt},
                            "usage": {"input_tokens": spent[0], "output_tokens": spent[1]},
                            "answer": answer,
                        },
                        ensure_ascii=False,
                        indent=1,
                    ),
                    encoding="utf-8",
                )
                return answer
            user = (
                prompt
                + "\n\nYour previous answer was rejected by the checker:\n- "
                + "\n- ".join(problems)
                + "\nAnswer again, fixing these points."
            )
        raise ValueError(f"{task}: answer failed checks after retries: {problems}")

    def cost_usd(self, replayed: bool = False) -> float:
        p_in, p_out = config.PRICE_PER_MTOK.get(config.MODEL, (0.0, 0.0))
        tin, tout = (self.replayed_in, self.replayed_out) if replayed else (self.tokens_in, self.tokens_out)
        return (tin * p_in + tout * p_out) / 1e6

    def summary(self) -> dict:
        return {
            "mode": self.mode,
            "model": config.MODEL,
            "api_calls": self.calls,
            "recorded_answers_used": self.cache_hits,
            "input_tokens": self.tokens_in,
            "output_tokens": self.tokens_out,
            "estimated_cost_usd": round(self.cost_usd(), 5),
        }

    @staticmethod
    def problems(answer: dict, schema: dict, check=None) -> list[str]:
        if "_error" in answer:
            return [answer["_error"]]
        try:
            jsonschema.validate(answer, schema)
        except jsonschema.ValidationError as e:
            return [f"schema: {e.message}"]
        return check(answer) if check else []

    # ----------------------------------------------------------------- private
    def _call(self, system: str, user: str, schema: dict, max_tokens: int, effort: str = "low"):
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"Call cap reached ({self.max_calls} per run).")
        self.calls += 1
        response = self._with_backoff(
            lambda: self._client.messages.create(
                model=config.MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                thinking={"type": "disabled"} if effort == "low" else {"type": "adaptive"},
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            )
        )
        usage = (response.usage.input_tokens, response.usage.output_tokens)
        self.tokens_in += usage[0]
        self.tokens_out += usage[1]
        if response.stop_reason in ("refusal", "max_tokens"):
            return {"_error": response.stop_reason}, usage
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text), usage
        except json.JSONDecodeError:
            return {"_error": "invalid JSON"}, usage

    def _with_backoff(self, send):
        import anthropic

        for attempt in range(config.NETWORK_RETRIES + 1):
            try:
                return send()
            except (
                anthropic.RateLimitError,
                anthropic.InternalServerError,
                anthropic.APIConnectionError,
            ) as e:  # timeouts are APIConnectionError
                if attempt == config.NETWORK_RETRIES:
                    raise
                delay = config.BACKOFF_BASE_S * 2**attempt + random.uniform(0, 0.5)
                self._log("retry", "-", "backoff", problems=[type(e).__name__], attempt=attempt)
                self.sleep(delay)

    def _log(self, task, key, source, usage=(0, 0), problems=(), attempt=0, latency_ms=0):
        line = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "task": task,
            "request": key,
            "source": source,
            "attempt": attempt,
            "model": config.MODEL,
            "input_tokens": usage[0],
            "output_tokens": usage[1],
            "latency_ms": latency_ms,
            "problems": list(problems),
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
