# Runbook

## Setup
1. Python 3.10+. `pip install -r requirements.txt` (only the API pieces need it).
2. `cp .env.example .env` and fill only what you use. Only the triage and the live evals need `ANTHROPIC_API_KEY`;
   without it they replay recorded answers (demo mode). Never commit `.env`.
3. To activate the hook in Claude Code: copy `.claude/settings.example.json` to `.claude/settings.json`.

## Routine operations
| Task | Command |
|---|---|
| Run all tests | `python -m unittest discover -s tests` |
| Validate a Todoist batch (opens the gate on success) | `python src/todoist_gate/check_batch.py <batch.json>` |
| Validate without opening the gate | add `--no-gate` |
| Approve a schedule-rule change / a delete (after the human's ok) | `python src/todoist_gate/release.py I7` / `DELETE` |
| Close approvals | `python src/todoist_gate/release.py --close` |
| Job-board delta | `python src/career/job_delta.py config/sources.csv out/` |
| LLM triage of the delta (capped) | `python src/career/triage.py out/ --max 10` |
| Evals, replaying recorded answers | `python src/agent_evals/run_evals.py --demo` |
| Evals, live (after changing the skill or the cases) | `python src/agent_evals/run_evals.py --max 40` |
| Anki | see the anki-librarian-mcp repository |
| Optimizer queue | `python src/optimizer/queue.py <root> [--dry]` |
| Audit a public HTML | `python src/privacy/public_filter.py page.html` |

## When something breaks
| Symptom | Cause | Fix |
|---|---|---|
| `BLOCKED (gate)` on add/reschedule | batch not validated in the last 15 min | run `check_batch.py`; fix every error until `BATCH CLOSED` |
| `BLOCKED (R2)` | tried to change a date via update-tasks | use reschedule-tasks; if it is an approved rule change, `release.py I7` |
| `Flag ... older than 15 minutes` | approval expired | ask the human again; recreate the flag only after a new ok |
| `BATCH OPEN` with `DECISIONS` | the plan does not fit (budget, dependency) | ask the human which task to prune or move; do not cram |
| `NoRecording` | demo mode (no key) and the request changed since it was recorded | run once with a key, or revert the change |
| `BudgetExceeded` | the run reached its call cap | raise `--max` / `AGENTS_MAX_CALLS` on purpose; what was left is triaged next run |
| `answer failed checks after retries` | the model broke a business rule twice | read the log line (`logs/`); fix the prompt or the profile, never loosen the check silently |
| Eval score below the gate in CI | a change in the skill or the cases made a case fail | read `evals/last-run.md`; fix the skill (or the case, if it was ambiguous), re-run live, commit the new recordings |
| `JUDGE TOO LENIENT` | the judge passed a deliberately wrong answer | the run is invalid; tighten the judge prompt before trusting any score |
| `error: ...` rows in the job delta | site down or layout changed | the run continues; check the source next run |
| Public filter `ABORT` | a forbidden term reached the rendered page | fix the allowlist or the generator; never bypass the audit |

## Change procedure
1. Change the code; add a test that reproduces the case.
2. Run the whole suite.
3. Commit only the paths you touched, one batch per commit. Never push from an agent session.
