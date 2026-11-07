"""Command line interface for the spaced repetition scheduler.

Commands:
  import   Import cards from a CSV (front, back, tag)
  list     Show every card in the collection
  today    Print today's due queue in the terminal (or plain HTML with --html)
  review   Interactive review session with 0-5 quality ratings
  rate     Rate one card non-interactively (for scripts)
  polish   Optionally rewrite card wording via an OpenAI-compatible endpoint
  stats    Collection and review counts
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import __version__
from .polish import (DEFAULT_API_KEY_ENV, DEFAULT_BASE_URL, DEFAULT_TIMEOUT,
                     api_key_from_env, polish_card)
from .queue import html_view, terminal_view, update_queue
from .scheduler import apply_review, is_due
from .store import Store, find_card, import_cards


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srs",
        description="SM-2 style spaced repetition scheduler for anything. Works offline.",
    )
    parser.add_argument("--data", type=Path, default=None,
                        help="collection JSON file (or set SRS_DATA; default ~/.spaced-repetition-scheduler/cards.json)")
    parser.add_argument("--version", action="version", version=f"srs {__version__}")
    commands = parser.add_subparsers(dest="command")

    def command(name, **kwargs):
        sub = commands.add_parser(name, **kwargs)
        sub.add_argument("--data", dest="data", type=Path, default=argparse.SUPPRESS,
                         help="collection JSON file (overrides the --data given before a subcommand)")
        return sub

    imp = command("import", help="import cards from CSV (columns: front, back, tag)")
    imp.add_argument("csv_file", type=Path)
    imp.add_argument("--tag", default="", help="tag applied to rows missing one")

    command("list", help="show all cards")

    today = command("today", help="print today's due queue (terminal) or an HTML file")
    today.add_argument("--html", type=Path, default=None, help="write plain HTML to this path instead")
    today.add_argument("--today-date", default=None, help="override today's date, YYYY-MM-DD")

    command("review", help="interactive review of due cards")

    rate = command("rate", help="rate one card without an interactive session")
    rate.add_argument("card", help="card id or exact front text")
    rate.add_argument("quality", type=int, choices=range(0, 6), help="review quality 0-5")
    rate.add_argument("--date", default=None, help="override review date, YYYY-MM-DD")

    polish = command("polish", help="rewrite card wording via an OpenAI-compatible endpoint")
    polish.add_argument("--base-url", default=DEFAULT_BASE_URL, help="default: %s (Ollama)" % DEFAULT_BASE_URL)
    polish.add_argument("--model", default=None, help="model name (env SRS_LLM_MODEL)")
    polish.add_argument("--limit", type=int, default=5, help="max cards to polish in one run")
    polish.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"seconds to wait for the endpoint (default: {DEFAULT_TIMEOUT})")
    polish.add_argument("--max-tokens", type=int, default=None,
                        help="optional max_tokens to cap a chatty endpoint")
    polish.add_argument("--tag", default=None, help="only polish cards with this tag")
    polish.add_argument("--apply", action="store_true", help="save polished wording (default: preview only)")
    polish.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV, help="env var holding a key, if any")

    command("stats", help="collection summary")

    return parser


def cmd_import(args) -> int:
    store = Store(args.data)
    cards = store.cards
    result = import_cards(cards, args.csv_file, default_tag=args.tag)
    store.save(cards)
    print(f"Imported {result['added']} card(s) from {args.csv_file} ({result['skipped']} skipped: "
          "missing front/back or duplicate).")
    return 0


def cmd_list(args) -> int:
    cards = Store(args.data).cards
    if not cards:
        print("Collection is empty. Import a CSV first: srs import sample_cards.csv")
        return 0
    print(f"{len(cards)} card(s):")
    for card in cards:
        marker = "*" if is_due(card) else " "
        print(f"{marker} [{card['tag'] or 'untagged'}] {card['front']} :: {card['back']}  "
              f"(reps {card['repetitions']}, EF {card['ease_factor']}, due {card['due']})")
    return 0


def cmd_today(args) -> int:
    cards = Store(args.data).cards
    today = date.fromisoformat(args.today_date) if args.today_date else date.today()
    buckets = update_queue([card for card in cards if card["front"].strip()], today)
    if args.html:
        args.html.write_text(html_view(buckets, today), encoding="utf-8")
        print(f"Wrote {args.html} ({len(buckets['overdue'] + buckets['today'])} due, "
              f"{len(buckets['tomorrow'])} tomorrow).")
    else:
        print(terminal_view(buckets, today))
    return 0


def cmd_review(args) -> int:
    store = Store(args.data)
    cards = store.cards
    queue = update_queue(cards)
    due_cards = queue["overdue"] + queue["today"]
    if not due_cards:
        print("Nothing due right now - the queue is clear.")
        return 0
    print(f"{len(due_cards)} card(s) due. Answer, press Enter, then rate your recall 0-5.\n")
    rated = 0
    for index, card in enumerate(due_cards, start=1):
        print(f"({index}/{len(due_cards)}) [{card['tag'] or 'untagged'}] {card['front']}")
        try:
            input("  (press Enter to reveal) ")
        except (EOFError, KeyboardInterrupt):
            break
        tag = card["tag"] or "untagged"
        print(f"  {card['back']}  [tag: {tag}]")
        quality = _prompt_quality()
        if quality is None:
            break
        apply_review(card, quality)
        rated += 1
        print(f"  Rescheduled. Next due {card['due']} (interval {card['interval_days']} day(s))\n")
    store.save(cards)
    print(f"Finished: {rated} card(s) rated, rest skipped unscheduled.")
    return 0


def _prompt_quality() -> int | None:
    while True:
        try:
            raw = input("  Quality 0-5 (0-2 forgot, 4 good, 5 easy; Enter to skip, q to quit): ")
        except (EOFError, KeyboardInterrupt):
            return None
        raw = raw.strip().lower()
        if raw == "q":
            return None
        if raw == "":
            return None
        if raw.isdigit() and 0 <= int(raw) <= 5:
            return int(raw)
        print("  Please enter a number 0-5.")


def cmd_rate(args) -> int:
    store = Store(args.data)
    cards = store.cards
    card = find_card(cards, args.card)
    if card is None:
        print(f"error: no unique card matches {args.card!r}", file=sys.stderr)
        return 1
    when = date.fromisoformat(args.date) if args.date else date.today()
    apply_review(card, args.quality, today=when)
    store.save(cards)
    print(f"Rated {args.quality}: next due {card['due']} (interval {card['interval_days']} day(s), "
          f"EF {card['ease_factor']}).")
    return 0


def cmd_polish(args) -> int:
    store = Store(args.data)
    cards = store.cards
    model = args.model

    if not model:
        print("error: no model given (use --model or set SRS_LLM_MODEL)", file=sys.stderr)
        return 1
    candidates = [card for card in cards if args.tag is None or card["tag"] == args.tag]
    if not candidates:
        print("No cards match; nothing to polish.")
        return 0
    preview, printed = [], 0
    api_key = api_key_from_env(args.api_key_env)
    for card in candidates[: max(args.limit, 0)]:
        print(f"Polishing [{card['tag'] or 'untagged'}] {card['front']}", flush=True)
        try:
            polished = polish_card(card["front"], card["back"], base_url=args.base_url,
                                   model=model, api_key=api_key, timeout=args.timeout,
                                   max_tokens=args.max_tokens)
        except (RuntimeError, ValueError) as err:
            print(f"  failed: {err}", file=sys.stderr)
            return 1
        print(f"  before : {card['front']} :: {card['back']}")
        print(f"  after  : {polished['front']} :: {polished['back']}")
        preview.append((card, polished))
        printed += 1
    if not args.apply:
        print(f"\nPreview only - {printed} card(s) polished in memory. Re-run with --apply to save these.")
        return 0
    for card, polished in preview:
        card["front"], card["back"] = polished["front"], polished["back"]
    store.save(cards)
    print(f"Saved polished wording for {len(preview)} card(s).")
    return 0


def cmd_stats(args) -> int:
    store = Store(args.data)
    cards = store.cards
    buckets = update_queue(cards)
    reviews = sum(len(card["history"]) for card in cards)
    print(f"Cards: {len(cards)}")
    print(f"Due today (incl. overdue): {len(buckets['overdue']) + len(buckets['today'])}")
    print(f"Due tomorrow: {len(buckets['tomorrow'])}")
    print(f"Scheduled later: {len(buckets['later'])}")
    print(f"Reviews recorded: {reviews}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "import":
        return cmd_import(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "today":
        return cmd_today(args)
    if args.command == "review":
        return cmd_review(args)
    if args.command == "rate":
        return cmd_rate(args)
    if args.command == "polish":
        return cmd_polish(args)
    if args.command == "stats":
        return cmd_stats(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
