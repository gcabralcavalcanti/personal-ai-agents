# Anki pipeline - one fictitious run, stage by stage

Topic: a finished study project on the **Taylor rule** (monetary policy). All content is illustrative.

## Stage 0 - Harvest (debrief)
Classifies the project first (study vs. work case vs. tool learning), then extracts only what that kind admits.

```
Project style: study (theory) - objective: deep study
Concepts harvested:
  - Taylor rule: policy rate reacts to inflation gap and output gap
  - Taylor principle: rate must move more than one-for-one with inflation
  - Neutral real rate (r*): rate that neither stimulates nor contracts
Talking points for interviews: none (pure theory)
```

## Stage 1 - Planner (reconcile mode)
Searches the live collection by keyword AND tag before proposing anything.

```
ALREADY HAVE  "Neutral real rate"   deck Economics::Macro  (active, 3 reviews)  -> do not duplicate
GAP           "Taylor rule"         -> 1 map card + 2 atomic cards
GAP           "Taylor principle"    -> 1 atomic card + 1 applied card
Order: map -> rule -> principle -> applied
```

## Stage 2 - Generator
Writes the cards as TSV (front, back, tags), respecting size and cognitive-load ceilings. See `cards.tsv`.

## Stage 3 - Tags
Normalizes tags into the library-style hierarchy (`Economics::Macro::MonetaryPolicy`), touching nothing else.

## Gate before writing
`importer --check` (dry run) -> load gate (cognitive weight per card) -> human approves in chat ->
`importer --ok` writes through the Anki lock (public version: the anki-librarian-mcp repository) -> reads every
created note back to confirm fields, tags and deck.
