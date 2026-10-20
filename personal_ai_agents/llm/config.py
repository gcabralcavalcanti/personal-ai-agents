"""Model choice, paths and cost limits for every script that calls the Claude API.

Everything that can cost money is capped here. The account behind this repo runs on a fixed monthly
credit with no card on file, so the defaults are deliberately small.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = ROOT / "data" / "recorded"  # recorded answers: response cache + demo mode (versioned)
LOGS = ROOT / "output" / "logs"  # one JSON line per call (not versioned)
SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"  # JSON Schemas for every structured answer

# Cheapest current model that handles short classification and judging.
MODEL = os.environ.get("AGENTS_MODEL", "claude-haiku-5-5")
PRICE_PER_MTOK = {"claude-haiku-5-5": (0.10, 0.50)}  # USD (input, output), Anthropic price list

MAX_CALLS_PER_RUN = int(os.environ.get("AGENTS_MAX_CALLS", "30"))
MAX_TOKENS = 600  # per answer: every schema here is small
TIMEOUT_S = 30.0  # per HTTP attempt
NETWORK_RETRIES = 3  # our own exponential backoff on 429 / 5xx / connection errors
BACKOFF_BASE_S = 1.0
SCHEMA_RETRIES = 1  # one extra call if the answer fails the schema or the semantic check
