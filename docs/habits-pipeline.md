# Habits (data pipeline agent)

## Problem
A habit-tracking phone app exports raw data. Turning it into weekly KPIs by hand was slow and
inconsistent, and the result mixes information that can be shown with information that never should.

## How it works
```
phone app backup (SQLite) -> converter -> spreadsheet (the database) -> HTML dashboard (private)
                                                                   \-> public dashboard (filtered)
```
- A scheduled weekly routine picks up the newest export from a synced folder, converts it, regenerates the
  spreadsheet and the dashboard. Habits are matched by the app's stable UUID, not by name (names change).
- Rolling 14/30/90-day views with traffic-light thresholds; goals come from a separate goals file owned
  by another agent (this one measures, it does not decide goals).
- The task manager is read-only for this agent (completion data as a productivity signal).

## Guardrails
- Writes the spreadsheet only with the human's ok; read-only on the task manager.
- Archived habits are retired automatically from the source flag, not from a manual list.
- **Privacy by default** for the public version (`src/privacy/public_filter.py` shows the pattern):
  allowlist of habit IDs + a denylist audit of the rendered HTML; one hit aborts and nothing is written.

## Tests
- **A/B snapshot test**: runs the real scripts on frozen inputs with an injected date in a temp copy and
  compares every output with a stored snapshot. Intentional output changes require regenerating the
  snapshot and saying why in the commit.
- Backup-vs-CSV equivalence test: the new SQLite path must produce cell-by-cell the same spreadsheet as the
  old CSV path for the same day.
- This repo: `tests/test_public_filter.py`.

## Example (fictitious)
```
habits in export: H01 Read 20 pages, H02 Medical check-up, H07 Language practice, H12 Evening walk
allowlist:        H01, H02, H07        refused category: health
public dashboard: H01, H07
audit:            OK: audit clean
```
