# Spaced Repetition Scheduler CLI

A tiny Python command-line tool that schedules review of anything. Import question
cards from CSV, get an SM-2 style interval per card, and print today's queue in the
terminal or a plain HTML page with due/tomorrow buckets. Everything works offline.
The only optional network feature is polishing card wording through your own
OpenAI-compatible endpoint (Ollama included, no keys needed).

Built and maintained by **Asdale Dynamics, LLC** as part of Dylan Asdale's
beginner-friendly, local-first AI toolset (see his book *The Massive AI Manual* and
the hub at dylanasdale.github.io). This tool schedules reviews; it does not quiz you
on facts like a flashcard game or a website template. The only nudge is "here is
what's due, rate yourself honestly."

## Why this tool

- **Local-first**: one JSON file holds your whole collection. No accounts, no servers.
- **Beginner-friendly**: plain English prompts, short commands, sensible defaults.
- **SM-2 math you can trust**: intervals and queue math are covered by pytest.
- **Bring your own model**: polish wording locally through Ollama's OpenAI-compatible
  endpoint, or any other `/chat/completions` server. API keys are optional and are
  never logged, printed or stored.

## Install

```bash
python3 -m pip install -e .[dev]      # from this folder, for development
```

Python 3.9+ is all it needs (standard library only).

## Quickstart

```bash
srs import sample_cards.csv           # cards, from a CSV with front, back, tag
srs today                             # terminal queue: overdue + due today + tomorrow
srs today --html review_queue.html    # plain HTML (no JS, no network requests) instead
srs review                            # interactive: reveal back, rate recall 0-5
srs stats                             # collection summary
srs list                              # every card with its schedule
```

`--data PATH` (or the `SRS_DATA` environment variable) points to your collection
file if you don't want the default `~/.spaced-repetition-scheduler/cards.json`.

### CSV format

The first row is a header; columns `front`, `back` and `tag` (case-insensitive).
Tag is optional and can be filled with `--tag SM2` for rows that leave it blank.
Duplicate fronts (case-insensitive) are skipped, so re-importing a file is safe.

```csv
front,back,tag
"SM-2: interval after the first success?","1 day.",sm2
"What is an OpenAI-compatible endpoint?","A server exposing /chat/completions with OpenAI-style JSON.",ai
```

See `sample_cards.csv` for a ready-to-run example.

### Review quality (0-5)

Follows SuperMemo SM-2 so it's easy to explain to a friend:

- **0-2**: forgot. The schedule resets to 1 day.
- **3**: remembered, barely. Interval advances, ease factor falls.
- **4**: good, standard memory (the default-ish choice).
- **5**: easy. Ease factor rises, interval grows faster.

After two successes (intervals 1, 6 days) the next interval is
`previous interval x ease factor`. Ease factor never falls below 1.3.

## Optional LLM polish

Rewrite card wording with an OpenAI-compatible endpoint. It is off by default and
never required. Ollama is the friendliest option because it takes no API key:

```bash
# Ollama, no keys, needs "ollama serve" already running
srs polish --model granite4.2:3b          # local Ollama default: http://localhost:11434/v1
srs polish --base-url http://localhost:1234/v1 --model qwen2.5 \
    --limit 3 --tag nursing              # any OpenAI-compatible server
srs polish --model gemma3 --apply         # preview first, then save changes
srs polish --model qwen3.5:4b --timeout 120 --max-tokens 1200   # chatty endpoints
```

Behavior:

- Default is **preview only**; `--apply` writes the polished wording back.
- Model name comes from `--model` or `SRS_LLM_MODEL`.
- If your endpoint needs a key, set it in an environment variable and name the
  variable with `--api-key-env` (default: `SRS_API_KEY`). The value is read at call
  time and never written anywhere.
- The prompt asks for a clear front and a short back, keeps meaning, adds no facts.
- Reasoning-style models (incl. newer Ollama builds) sometimes answer in a
  `reasoning` field with empty `content`; the client falls back to reading that.

## Differences from sibling tools

- **vocab-quiz-builder-cli** quizzes you on vocabulary; this schedules reviews.
- **csv-flashcards-site-template** turns CSVs into a study website; this is a
  command-line scheduler that won't hold your cards online.

## Development

```bash
python3 -m pytest          # 42 tests cover intervals, queue math, CLI and polish
```

Layout:

```
srs_scheduler/
  scheduler.py  SM-2 math: interval, ease factor, one review applied
  queue.py      due/tomorrow buckets + terminal and plain-HTML renderings
  store.py      JSON collection (local-first) and CSV import
  polish.py     OpenAI-compatible polish client (Ollama-friendly)
  cli.py        argparse commands: import, list, today, review, rate, polish, stats
```

## License

MIT - Copyright (c) 2026 Asdale Dynamics, LLC. See `LICENSE`.
