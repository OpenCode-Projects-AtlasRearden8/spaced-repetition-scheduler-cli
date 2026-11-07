# STATUS.md - Spaced Repetition Scheduler CLI

Last updated: 2026-11-07
Version: 0.1.0
Owner: Asdale Dynamics, LLC

## What was built

A Python 3.9+ command line tool (`srs`, package `spaced-repetition-scheduler-cli`)
that schedules review of anything:

- **CSV import** - question cards with `front`, `back`, `tag` columns
  (case-insensitive header, optional tag with `--tag` default, BOM-safe,
  duplicate-safe by front text).
- **SM-2 style scheduling** - per-card ease factor (default 2.5, floor 1.3),
  0-5 quality ratings: forgotten (0-2) resets to 1 day, 1 and 6 day ladder for
  the first successes, then `previous interval x ease factor`, never smaller.
- **Today's queue** - terminal output or plain HTML (no JS/external assets,
  works offline) with overdue, due-today and due-tomorrow buckets, always
  showing due/tomorrow counts.
- **Review flow** - interactive `review` (reveal back, rate recall) plus a
  script-friendly `rate <card> <0-5> [--date YYYY-MM-DD]` for testing and
  automation.
- **Optional LLM polish** - previews/rewrites card wording through any
  OpenAI-compatible `/chat/completions` endpoint. Ollama by default
  (`http://localhost:11434/v1`, no key). API keys are only read from an
  environment variable named via `--api-key-env` (default `SRS_API_KEY`) and
  are never stored, logged or written to files. Preview-only unless `--apply`.
  Falls back to `message.reasoning` when a reasoning-style model answers with
  empty `content`.
- **Local-first storage** - one JSON file
  (`~/.spaced-repetition-scheduler/cards.json`, configurable via `SRS_DATA` or
  `--data`). Atomic writes (tmp-file + rename).

Layout: `srs_scheduler/scheduler.py` (SM-2 math), `queue.py` (buckets +
rendering), `store.py` (JSON collection + CSV import), `polish.py`
(OpenAI-compatible client), `cli.py` (argparse CLI).

## How to run it

```bash
python3 -m pip install -e .[dev]      # or use a venv
srs import sample_cards.csv
srs today                             # terminal queue
srs today --html review_queue.html    # plain HTML with due/tomorrow buckets
srs review                            # interactive 0-5 ratings
srs rate "SM-2: interval after the first success (quality >= 3)?" 4
srs polish --model <ollama-model> [--apply] [--timeout N] [--max-tokens N]
srs stats | list --help               # summary; full help
```

## Verification results (2026-11-07)

- `python -m pytest -q`: **42 passed** (intervals, queue buckets/ordering, CSV
  import edge cases incl. BOM, CLI end-to-end via temp data files, polish
  client against a local stub endpoint, HTML escaping, offline checks).
- `python -m build`: sdist + wheel build cleanly.
- Editable install exposes `srs` entry point; `srs --version`, `--help` OK.
- Live end-to-end: imported `sample_cards.csv` (6 cards), rated a card with
  `--date`, printed the terminal queue (5 due / 1 tomorrow), wrote the HTML
  queue, ran `stats`, and ran `srs polish` against real local Ollama
  (`granite4.2:3b`) - parsed the model JSON and showed before/after, preview
  only as designed.
- No secrets or personal data anywhere in the repo; only env vars by name.

## Known gaps

- Only one rating per day is recorded; no mid-day repetition (SM-2 "same day"
  steps not implemented).
- `review` and `stats` have no `--today-date` override yet (`rate`, `today` do),
  so interactive review always uses the real calendar date.
- HTML uses Python's `html.escape`-only rendering of card text; rich text
  (markdown, images, LaTeX) is out of scope.
- Polish applies the same prompt to every card; no back/front consistency
  checks (e.g. comparing meaning) beyond trusting the model.
- No multi-collection/concurrent-writes handling beyond atomic rename (two
  simultaneous `srs` processes could race on save).
- Only Ollama-style defaults tested live; other OpenAI-compatible servers are
  supported by spec but untested in anger.
- Tags are free text; no tag list/autocomplete UI command.
