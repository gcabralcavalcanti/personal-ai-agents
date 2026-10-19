"""One trace.jsonl per run: stage, status, duration, model calls, tokens and cost.

    tr = Trace("demo", llm)
    with tr.step("planner", round=1) as s:
        s["status"] = "blocked"      # ok by default; blocked | error | skipped
    tr.close()

Answers replayed from recordings report what they cost when recorded (recorded_cost_usd).
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Trace:
    def __init__(self, name: str, llm=None, root: Path | None = None):
        self.llm = llm
        self.run_id = f"{name}-{datetime.now():%Y%m%d-%H%M%S}"
        self.dir = Path(root or ROOT / "runs") / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "trace.jsonl"
        self.t0 = time.monotonic()
        self.steps: list[dict] = []

    def _usage(self) -> tuple:
        """calls, replayed answers, tokens in/out (live + replayed), cost paid now, cost when recorded."""
        m = self.llm
        if m is None:
            return 0, 0, 0, 0, 0.0, 0.0
        return (
            m.calls,
            m.cache_hits,
            m.tokens_in + m.replayed_in,
            m.tokens_out + m.replayed_out,
            m.cost_usd(),
            m.cost_usd(replayed=True),
        )

    @contextmanager
    def step(self, stage: str, **meta):
        before, t0 = self._usage(), time.monotonic()
        rec: dict = {"stage": stage, **meta, "status": "ok", "detail": ""}
        try:
            yield rec
        except Exception as e:
            rec["status"], rec["detail"] = "error", f"{type(e).__name__}: {e}"[:300]
            raise
        finally:
            after = self._usage()
            rec.update(
                duration_ms=int((time.monotonic() - t0) * 1000),
                api_calls=after[0] - before[0],
                recorded_answers=after[1] - before[1],
                input_tokens=after[2] - before[2],
                output_tokens=after[3] - before[3],
                cost_usd=round(after[4] - before[4], 6),
                recorded_cost_usd=round(after[5] - before[5], 6),
                ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            self.steps.append(rec)
            self._write(rec)

    def close(self, **meta) -> dict:
        tot = {
            k: sum(s[k] for s in self.steps) for k in ("api_calls", "recorded_answers", "input_tokens", "output_tokens")
        }
        line = {
            "stage": "run",
            "run_id": self.run_id,
            **meta,
            **tot,
            "status": "error" if any(s["status"] == "error" for s in self.steps) else "ok",
            "duration_ms": int((time.monotonic() - self.t0) * 1000),
            "cost_usd": round(sum(s["cost_usd"] for s in self.steps), 6),
            "recorded_cost_usd": round(sum(s["recorded_cost_usd"] for s in self.steps), 6),
            "detail": f"{len(self.steps)} steps",
        }
        self._write(line)
        return line

    def _write(self, rec: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
