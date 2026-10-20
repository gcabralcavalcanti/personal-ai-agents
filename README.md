# personal-ai-agents

Small, runnable versions of the AI agents I use every day to run my calendar, habits, goals and job search, with
the safety rules that keep them from doing damage.

![Public excerpt of a private system](https://img.shields.io/badge/data-public%20excerpt%20of%20a%20private%20system-555)
![Built with AI assistance](https://img.shields.io/badge/built%20with-AI%20assistance-6b46c1)

## Results

| What happens | Where to see it |
|---|---|
| The calendar agent tries to change tasks before its plan was checked and is blocked; its first plan fails the checker and is sent back with the reasons; the second passes, and only then does the write go through | `python demo.py secretary` · [screenshot](docs/demo-secretary.png) |
| 35 real openings from public job boards sorted for an example candidate: 16 settled by simple rules with no AI call, 19 read by Claude, for about US$ 0.003 | [`output/career.html`](output/career.html) · [`output/triage_report.md`](output/triage_report.md) |
| 11 of 12 test requests handled the way the career agent's rules say; the grader also rejects the two wrong answers planted to check it | [`output/evals/scoreboard.csv`](output/evals/scoreboard.csv) · [`output/evals/last-run.md`](output/evals/last-run.md) |
| Goals scored from the data, next to how they feel: one goal feels like 4/10 and measures 8/10 | [`output/goals.html`](output/goals.html) |

![The four agents' pages](docs/demo-index.png)

## Run it

```
pip install -r requirements.txt
python demo.py
```

Runs without an API key, replaying recorded answers. Set `ANTHROPIC_API_KEY` to call Claude live (add `--live`).
It writes one page per agent to `output/` and opens the index. `python demo.py secretary` (or `habits`, `goals`,
`career`) runs one agent; the calendar agent asks before writing, and `--yes` approves without asking.

## How it works

Each agent is a folder of instructions and code that Claude follows inside Claude Code; the parts that can run on
their own are here, with fictitious data.

| Agent | What it does | Real app it works with |
|---|---|---|
| **Secretary** | plans and replans the day and the week; a script checks the whole plan, and a *hook* (a check Claude Code runs before every tool call) blocks any write to the calendar until the plan passed | Todoist |
| **Habits** | turns the phone app's export into a spreadsheet and a dashboard (14, 30 and 90 days) | Loop Habits |
| **Goals** | scores each key result from where it lives (habit app, task manager, a file that exists or not) and shows it next to how the goal feels | Todoist, Loop Habits |
| **Career** | reads public job boards, keeps only what changed since last week, and sorts new openings into apply, monitor or discard | public job boards, Claude API |
| Librarian | turns study material into flashcards with the same safety rules; lives in its own repository, [anki-librarian-mcp](https://github.com/gcabralcavalcanti/anki-librarian-mcp) | Anki |
| Optimizer | audits the other agents' folders and keeps a list of problems that closes itself when they are fixed | git |

![Secretary: the plan that passed, as a day timeline](docs/demo-secretary.png)

The rules every agent follows: read freely, write only after approval; check the whole plan in code before
writing (the model's confidence is not evidence); every past mistake becomes a check with a test; nothing private
leaves the computer. More: [`docs/design.md`](docs/design.md), the story behind one rule in
[`docs/case-study-recurrence-gate.md`](docs/case-study-recurrence-gate.md), and one page per agent in [`docs/`](docs/).
Operations and troubleshooting: [`RUNBOOK.md`](RUNBOOK.md).

| Habits | Goals | Career |
|---|---|---|
| ![Habits dashboard](docs/demo-habits.png) | ![Goals panel](docs/demo-goals.png) | ![Career openings](docs/demo-career.png) |

## Data

- Calendar, habits and goals: **fictitious**, written for the demo ([`data/`](data/)). The habit export is
  generated in the same format the Loop Habits app writes.
- Career: **real public job-board titles** from 19 Oct 2026
  ([`data/job_board_snapshot.json`](data/job_board_snapshot.json)) and an example candidate profile.
- Claude's answers for the demo are stored in [`data/recorded/`](data/recorded/) so every run can be replayed.
- The private system this comes from (600+ commits) is not here. Some files are close copies, others simplified
  versions; each file says which.

## Limits

- An excerpt: the real calendar checker has about 40 rules; the one here keeps the structure and a handful.
- The job triage reads only titles and places, so graduation dates usually come back "unknown".
- A plan can pass every check and still not be what you meant; that is why the human approval stays.
- The goals and memoir agents that work on private material are described, not included.

## Privacy & LGPD

Everything here is fictitious or public. Before anything personal leaves my computer it goes through a filter: an
allow-list of what may be shown and a scan for forbidden terms that stops publication on any hit
([`personal_ai_agents/privacy/`](personal_ai_agents/privacy/)). No personal record, name or credential is in this
repository.

## Using it with your own data

I run these agents every day on my real calendar, habits and goals, which stay private. If you want to adapt one
to your own tools, open an issue and I can help.

## How AI was used

I use Claude (Claude Code and the API) for coding, review and documentation. The questions, modelling choices,
validation and conclusions are mine.

## License

MIT, Guilherme Cabral.
