# personal-ai-agents

**[See it working](https://gcabralcavalcanti.github.io/personal-ai-agents/)** · [Overview, 1 page (PDF)](overview.pdf)

Small, runnable versions of the AI agents I use every day to run my calendar, habits, goals, study and job search,
with the safety rules that keep them from doing damage.

**Result:** the career agent passes 11 of 12 test requests, each answer scored by a second AI
([last run](output/evals/last-run.md)).

![Public excerpt of a private system](https://img.shields.io/badge/data-public%20excerpt%20of%20a%20private%20system-555)
![Built with AI assistance](https://img.shields.io/badge/built%20with-AI%20assistance-6b46c1)

![The agents' pages](docs/demo-index.png)

## What it shows

- **A calendar agent that cannot write a bad plan.** Its first plan fails the checker and goes back with the
  reasons; only a plan that passes, and that you approve, reaches the calendar.
- **Flashcards meet the calendar.** The review forecast of each deck becomes study blocks that fit the free slots
  of the week, through the same checker.
- **Habits, goals and jobs from real formats.** The habit app's export becomes a dashboard, goals are scored from
  the data next to how they feel, and public job openings are sorted into apply, monitor or discard.

**The method behind them.** I organise study and work in four kinds of session, A.F.A.M.: Architecting (build the
material), Frameact (solve the problem), Anking (review in Anki) and Maintenance (keep a project running, no new
features). The calendar and study agents plan the week around them. A Maintenance session does only the operational
work that keeps a project going (the weekly calendar cleanup, the audit round, a check of the flashcard collection);
a feature idea that comes up there becomes its own Architecting or Frameact task. On a given day, within one project,
Maintenance comes last.

## Run it

```
pip install -r requirements.txt
python demo.py
```

Runs without an API key, replaying recorded answers. Set `ANTHROPIC_API_KEY` and add `--live` to call Claude live.

## How I use it

The Secretary every day, when I ask. The others mostly prepare the week on Thursday night as scheduled tasks
(habits dashboard, job openings, flashcard radar), and the Optimizer sends me a summary before morning. They
propose; I approve. Who runs on its own and what I ask for: [How I use it](docs/how-it-works.md#how-i-use-it).

## More

- [How it works](docs/how-it-works.md): how I use it, each agent and its rules, the data, the options, and how to
  run every agent on your own files (Loop Habits, Todoist, Anki).
- [Runbook](RUNBOOK.md): setup, routine commands, updating, and what to do when something breaks.
- Everything here is fictitious or public; how personal data is kept out is in
  [How it works](docs/how-it-works.md#privacy--lgpd).

## Limits

- An excerpt of a private system: the real calendar checker has many more rules than the one here.
- A plan can pass every check and still not be what you meant; that is why the human approval stays.
- The agents that work on private material (goals review, memoir) are described, not included.

## How AI was used

I use Claude (Claude Code and the API) for coding, review and documentation. The questions, modelling choices,
validation and conclusions are mine.

## License

MIT, Guilherme Cabral.
