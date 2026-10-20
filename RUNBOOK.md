# Runbook

## Setup
1. Python 3.10+. `pip install -r requirements.txt`.
2. `cp .env.example .env` and fill only what you use. Only the triage and the live evals need `ANTHROPIC_API_KEY`;
   without it they replay recorded answers (demo mode). Never commit `.env`.
3. To switch on the hook (the check Claude Code runs before every Todoist write) copy
   `.claude/settings.example.json` to `.claude/settings.json`.

## Routine operations
| Task | Command |
|---|---|
| Live demo on GitHub Pages | every push to main runs `.github/workflows/pages.yml` (no key) and publishes `output/*.html`; turn it on once in Settings > Pages > Source = GitHub Actions |
| Run all tests | `python -m unittest discover -s tests` |
| All agents' demo pages (no key) | `python demo.py` → `output/index.html` · `--no-open` keeps the browser closed |
| One agent | `python demo.py secretary` (or `habits`, `goals`, `career`, `study`) · `--yes` approves the calendar write without asking · `--live` calls Claude for answers not recorded yet |
| Your own data | `--input` (habit export or backup), `--goals`, `--sources`, `--profile`, `--board`, `--request`, `--week`; formats in [docs/how-it-works.md](docs/how-it-works.md#using-it-with-your-own-data) |
| Read Todoist into a board (read-only, needs `TODOIST_API_TOKEN`) | `python personal_ai_agents/todoist_gate/todoist_export.py --days 3 > my_board.json` |
| Read the Anki review forecast (read-only, Anki open with AnkiConnect) | `python personal_ai_agents/study/anki_forecast.py "Deck A" > forecast.json` |
| Show the last run's trace | `python personal_ai_agents/tracing/view.py --last` · HTML: add `--html trace.html` |
| Validate a Todoist batch (opens the gate on success) | `python personal_ai_agents/todoist_gate/check_batch.py <batch.json>` |
| Validate without opening the gate | add `--no-gate` |
| Approve a schedule-rule change / a delete (after the human's ok) | `python personal_ai_agents/todoist_gate/release.py I7` / `DELETE` |
| Close approvals | `python personal_ai_agents/todoist_gate/release.py --close` |
| Job-board delta (live, public pages) | `python personal_ai_agents/career/job_delta.py data/sources.csv out/` |
| LLM triage of the delta (capped) | `python personal_ai_agents/career/triage.py out/ --max 10` |
| Evals, replaying recorded answers | `python personal_ai_agents/agent_evals/run_evals.py --demo` |
| Evals, live (after changing the skill or the cases) | `python personal_ai_agents/agent_evals/run_evals.py --max 40` |
| Anki | see the anki-librarian-mcp repository |
| Optimizer queue | `python personal_ai_agents/optimizer/queue.py <root> [--dry]` |
| Audit a public HTML | `python personal_ai_agents/privacy/public_filter.py page.html` |

## Update
1. `git pull`, then `pip install -r requirements.txt`.
2. Changed a prompt, a skill, the eval cases or the demo board? Run the piece once live (`--live`, or
   `run_evals.py --max 40`) to record the new answers, check the result, and commit `data/recorded/`.
3. Changed the calendar rules? Add a test that reproduces the case before changing `check_batch.py`.
4. Run the tests and `python demo.py --no-open` before committing.

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
| Eval score below the gate in CI | a change in the skill or the cases made a case fail | read `output/evals/last-run.md`; fix the skill (or the case, if it was ambiguous), re-run live, commit the new recordings |
| Demo ends with `BATCH OPEN after 3 rounds` | the planner could not produce a valid batch (or said it could not fulfil the request) | intended outcome: nothing is written; read the validator report and the planner's open question |
| `JUDGE TOO LENIENT` | the judge passed a deliberately wrong answer | the run is invalid; tighten the judge prompt before trusting any score |
| `error: ...` rows in the job delta | site down or layout changed | the run continues; check the source next run |
| Public filter `ABORT` | a forbidden term reached the rendered page | fix the allowlist or the generator; never bypass the audit |

## Change procedure
1. Change the code; add a test that reproduces the case.
2. Run the whole suite.
3. Commit only the paths you touched, one batch per commit. Never push from an agent session.

## When a demo page looks wrong
| Symptom | Cause | Fix |
|---|---|---|
| `no recorded answer` / `NoRecording` | a prompt, the board or the cases changed since the recording | run that piece with `--live` and a key, or undo the change |
| Calendar page says "waiting for approval" | the run had no keyboard and no `--yes` | `python demo.py secretary --yes` |
| Habits page empty or missing | the export file was deleted | it is regenerated on the next run (`data/loop-habits-export.zip`, fictitious) |
| Study page lists a deck as "too few cards" | under 5 minutes of review a day | intended: no block is proposed; give it one by hand if you want it opened |
| `no deck named ...` from `anki_forecast.py` | deck name typed differently from Anki | copy the full name, with `::` for subdecks |
| `Set TODOIST_API_TOKEN` | no token in the environment or `.env` | add it to `.env`; an empty value counts as no token |
| A page did not open | `--no-open`, or no default browser | open `output/index.html` by hand |

