# Career agent (consultant + researcher)

## Problem
Applications to internships and trainee programs come from dozens of company pages with different formats and
deadlines. Checking them by hand is slow; letting an AI act freely on professional networks is risky.

## How it works
One skill that reads the request and picks a mode:

| Mode | Trigger (examples) | Output |
|---|---|---|
| Status (default) | "career agent", the weekly review | decisions ranked by priority + processes due in 30 days |
| Opportunity | "saw this opening", "should I apply to X" | verdict from the triage rules + a proposed task (with approval) |
| Preparation | "interview at X on Friday" | backwards plan per front: company, network, case, CV, logistics |
| Collection | weekly batch of pasted posts and screenshots | triage of what is new |
| Research | "who do I know at X", "draft a message to Y" | summary in chat; drafts only |
| CV and profile | "rewrite my CV" | draft from the real-history file; unsourced items marked [CONFIRM] |
| Study / Goals | "what should I study", "career goal this quarter" | proposal handed to the goals agent, which records it |

Three automated pieces in this repository:

1. **Job-board delta** (`personal_ai_agents/career/job_delta.py`): reads a list of public career pages, extracts entry-level
   titles (public Greenhouse API, or a text pattern on other pages) and reports only the **delta** since the last
   run. Idempotent: a second run with no change reports "unchanged".
2. **LLM triage** (`personal_ai_agents/career/triage.py`): every new opening gets a structured verdict from the Claude API
   (`personal_ai_agents/schemas/triage_verdict.json`): apply / monitor / discard, graduation fit, geography, preparation cost and a
   one-line reason. Code does what code can: seniority words discard an opening with no call, and the business
   rules are checked on the answer (an opening outside the geography can never be "apply"; a violation is sent
   back once with the complaint). Verdicts are stored by opening, so re-running costs nothing.
3. **Automated evals** (`personal_ai_agents/agent_evals/run_evals.py`): the skill's request cases run on their own, with the
   model as judge (details below).

## Guardrails
- Never opens the professional network site or anything behind a login, not even in a scheduled routine (blocked
  list in code); the human reads those pages and pastes.
- Never sends, publishes, connects or applies on the human's behalf: it drafts, the human acts.
- Decisions already recorded are not reopened without a new fact; when asked, it asks what changed.
- Every deadline carries a source and the date it was checked. No invented dates.
- Tasks go through the Secretary's validation gate, after the human's ok.

## Tests and evals
- **Request cases** (`tests/golden/career_cases.json`, 12 fictitious cases mirroring the reference cases of the private version): each has
  a request, a context, the accepted modes and the expected behaviours. The agent model answers from the skill
  (`personal_ai_agents/agent_evals/career_skill.md`) in a fixed JSON shape; code checks the mode; a separate judge call grades each
  behaviour without seeing the skill. Two **negative controls** (wrong answers) must be failed by the judge, or
  the run is invalid. Binary per case, as in production.
- **Scoreboard** (`output/evals/scoreboard.csv`): first live run 7/12; the failures pointed to three rules the skill
  stated too vaguely and two case items worded ambiguously; after the fix, 11/12. The remaining failure (K11:
  the agent refuses to read the network in a routine but does not say the routine stays on public sources) is
  kept visible. CI replays the recorded answers and fails if the score drops below 11.
- Unit tests without network: `tests/test_job_delta.py`, `tests/test_triage.py`, `tests/test_evals.py`.

## Example
Real public boards, example candidate profile (`output/triage_report.md`, first live run, 19 Oct 2026):
```
New openings: 35 · decided by code: 16 · by the model: 19 · API calls: 20 · estimated cost: US$ 0.00328
| monitor | BTG Pactual | Estágio Short Job / Automation - Development - São Paulo, Rio de Janeiro e Remoto | preferred | unknown | medium | Entry-level internship in a preferred city, but the title does not state accepted graduation dates ... |
| discard | EBANX | Treasury Analyst / India - Mumbai | outside | unknown | medium | Location Mumbai is outside the preferred and acceptable geographies ... |
```
