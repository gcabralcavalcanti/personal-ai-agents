# Librarian (Anki agent) and the card pipeline

> The code that reaches Anki lives in its own repository, **anki-librarian-mcp** (an MCP server with the
> same lock, plus dry-run plans, human approval, reconciliation and an audit log). This page documents the
> agent around it: what it decides, how the card pipeline is split, and the rules it follows.

## Problem
Spaced-repetition flashcards (Anki) are where long-term learning is stored: about a hundred decks, years of
review history. Two risks: a model generating cards in bulk (duplicates, bloated cards, inconsistent tags) and
a model touching the review history, which cannot be rebuilt.

## How it works
Two layers.

**1. The Librarian governs the collection** (it does not write cards). Four modules, chosen from the request:

| Module | Question it answers | Cadence |
|---|---|---|
| Deck strategy | Given this quarter's goals, which decks are active, parked or new? | quarterly, with the goals review |
| Pipeline and logistics | Which card skill runs now; how Anki, the task manager and the notes folder stay in sync; backups | on demand |
| Scheduler health (FSRS) | Is the retention target right; is the daily load sustainable; what to prune | every 6 weeks |
| Radars | Weekly scan of external sources per topic, turned into cards and tasks | weekly |

The live state of the collection (decks, presets, load, backlog) is a generated file, not prose: a script reads
the collection and rewrites it, so the agent never reasons from a stale number.

**2. The card pipeline**: four skills in sequence, each with one role.

| Stage | Role | Output |
|---|---|---|
| Harvest | debrief a finished project; classify it before extracting (study, work case, tool learning) | concepts + talking points |
| Planner | reconcile with the live collection (keyword AND tag search) | gaps vs. "already have", ordered plan |
| Generator | write cards to a fixed format (TSV), with size and cognitive-load ceilings | TSV |
| Tags | normalize tags to a library-style hierarchy (four areas + a "specific" branch), nothing else | tag changes |

Before anything is written, the importer runs: dry run -> cognitive-load gate (a weight per card; the batch has
a ceiling) -> front gate (target date and rubric on cards that need them) -> human approval -> write -> read every
created note back to confirm fields, tags and deck.

## Guardrails
| Rule | Enforced by |
|---|---|
| Reads are free; every write needs the human's ok, given after the proposal | client lock (`--ok`), in anki-librarian-mcp: plan + approval |
| Deleting notes or decks, rescheduling, resetting, answering cards, sync: forbidden to the agent | forbidden list, checked before any request is sent |
| Unknown actions are blocked (allowlist, not denylist) | client lock |
| Resetting a card only through one script, only for cards with 5 reviews or fewer | conditional action with its own criterion |
| The red flag ("this card is wrong") is the human's: the agent reads it, never writes it, never overwrites a flag it did not set | flag routine reads before and after |
| A tag update rewrites the whole list: re-read the note immediately before writing, never write from a snapshot | client + importer |
| Duplicates blocked collection-wide; "same front, different back" goes to the human | reconciliation |
| The source is the project folder; Anki is derived from it, never the other way round | pipeline order |

## Tests
Production: 7 test files with fake data (no Anki running): load gate, front gate, reposition criterion, filtered
decks, media, suspension routine, collection-state generator. The public server has its own suite with a fake
AnkiConnect (see anki-librarian-mcp).

## Example (fictitious)
See `examples/anki_pipeline.md` (one run, stage by stage) and `examples/cards.tsv`.
```
propose_add_notes("Economics::Macro", 3 notes)
  -> plan p-13af82, pending: 2 to add · skipped as duplicate: 1 (note 1700000000000) · similar flagged: 1 (score 0.92)
apply_plan("p-13af82")
  -> the human sees the plan in an approval form and approves
  -> applied: created 2, mismatched after write 0
propose_delete_notes([...])
  -> BLOCKED: deleteNotes is off. Turning it on is the human's decision (allow_delete = true in the config).
```
Full transcript (fake Anki, real server process): `examples/demo_transcript.md` in anki-librarian-mcp.
