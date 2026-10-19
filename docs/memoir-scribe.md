# Memoir scribe

> Architecture only. The memoir itself is private and is not in this repository. Every example is fictitious.

## Problem
A personal memoir kept for years: free writing, periodic reviews, notes from conversations. Asking a model to
"help write it" has an obvious failure mode: the model's paraphrase slowly replaces the author's voice, and a
reader can no longer tell what the person wrote from what the AI produced.

## How it works
A mode of the [goals & behavior analysis](goals-behavior-analysis.md) agent, and the only component allowed to
write in the memoir folder. The memoir is plain Markdown in git: one file per year, plus timeless pieces
(letters, poems) and timelines.

1. **Short interview.** At most three questions per message, from a question bank organised by goal area and by
   context ("you travelled last week: what stayed with you?").
2. **Compose in the author's style**, reading the last dated entry of the current year first to keep the tone.
3. **Show the exact text, wait for "ok"**, then append it to the year file. Raw captures go to an inbox folder
   (`YYYY-MM-DD-title.md`) and are woven in later, on command.

## Provenance (the core rule)
Every entry carries a label, and the label decides what may enter:

| Label | What it is | Enters when |
|---|---|---|
| `[written]` | the author's own text, verbatim | always (never edited, never "corrected") |
| `[session DD/MM]` | an exact transcription of what the author said in a conversation | the agent quotes the passage and asks "may I add this?"; only on yes |
| `[AI draft - approved DD/MM]` | an entry the scribe composed from the interview | only after ok on the final text |

**AI analysis never enters the memoir**: summaries, interpretations, scores and the agent's own mistakes go to
the analysis agent's case file. The memoir is the primary record; the analysis is derived from it, never the
other way round. Factual memory is not corrected: it is a record, not an edit.

## Guardrails
- Single writer: other agents read the memoir; only this mode writes.
- Consolidation or reorganisation only on explicit command; consumed raw captures move to an archive, nothing
  is deleted.
- Flashcards derived from the memoir (dates, milestones) flow folder -> Anki, through the Librarian's pipeline,
  never the reverse.
- Read in sessions on the computer only; nothing is synced to third-party note apps.

## Example (fictitious)
```
> memoir session
1/3  You marked "trip to the coast" as done on Saturday. What do you want to remember from it?
...
Draft for 2031 (to append under "Entries"):
  [AI draft - approved 14/03] Saturday at the coast with my brother: first time we talked about ...
OK to save? (yes / edit / no)
```
