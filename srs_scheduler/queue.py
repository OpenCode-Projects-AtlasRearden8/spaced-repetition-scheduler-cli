"""Queue math and rendering: today's due list and tomorrow's bucket.

The bucket math is deliberately separated from presentation so tests of interval
and queue math don't have to touch any strings.
"""

from __future__ import annotations

import html
from datetime import date, timedelta

from .scheduler import parse_date


def _sort_key(card: dict) -> tuple:
    return (parse_date(card["due"]), card["tag"].lower(), card["front"].lower())


def update_queue(cards: list[dict], today: date | None = None) -> dict:
    """Split cards into overdue, today and tomorrow buckets."""
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    buckets: dict[str, list] = {"overdue": [], "today": [], "tomorrow": [], "later": []}
    for card in cards:
        due = parse_date(card["due"])
        if due < today:
            buckets["overdue"].append(card)
        elif due == today:
            buckets["today"].append(card)
        elif due == tomorrow:
            buckets["tomorrow"].append(card)
        else:
            buckets["later"].append(card)
    for bucket in buckets.values():
        bucket.sort(key=_sort_key)
    return buckets


def format_line(card: dict) -> str:
    tag = card["tag"] or "untagged"
    return f"[{tag}] {card['front']} :: {card['back']}  (due {card['due']})"


def terminal_view(buckets: dict, today: date | None = None) -> str:
    today = today or date.today()
    due_all = buckets["overdue"] + buckets["today"]
    lines = [f"Today's review queue - {len(due_all)} card(s) due ({today.isoformat()}) - "
             f"{len(buckets['tomorrow'])} tomorrow"]
    if not due_all:
        lines.append("")
        lines.append("Nothing due today. Come back tomorrow!")
    else:
        for title, bucket in (("Overdue", buckets["overdue"]), ("Due today", buckets["today"])):
            if bucket:
                lines.append("")
                lines.append(f"{title} ({len(bucket)}):")
                lines.extend(f"  {format_line(card)}" for card in bucket)
    if buckets["tomorrow"]:
        lines.append("")
        lines.append(f"Due tomorrow ({len(buckets['tomorrow'])}):")
        lines.extend(f"  {format_line(card)}" for card in buckets["tomorrow"])
    return "\n".join(lines)


def _table(card: dict) -> str:
    esc = html.escape
    return (
        '  <tr>'
        f"<td>{esc(card['front'])}</td>"
        f"<td>{esc(card['back'])}</td>"
        f"<td>{esc(card['tag'] or '')}</td>"
        f"<td>{esc(card['due'])}</td>"
        "</tr>"
    )


def _section(title: str, cards: list[dict]) -> str:
    rows = "\n    ".join(_table(card) for card in cards)
    count = len(cards)
    plurality = "" if count == 1 else "s"
    return f"""<section>
  <h2>{html.escape(title)} ({count} card{plurality})</h2>
  <table>
    <thead>
      <tr><th>Front</th><th>Back</th><th>Tag</th><th>Due</th></tr>
    </thead>
    <tbody>
    {rows}
    </tbody>
  </table>
</section>"""


def html_view(buckets: dict, today: date | None = None, title: str = "Today's Review Queue") -> str:
    """Plain, dependency-free HTML with due/tomorrow buckets. Works offline."""
    today = today or date.today()
    due_all = buckets["overdue"] + buckets["today"]
    sections = []
    if due_all:
        sections.append(_section("Due today", due_all))
    if buckets["tomorrow"]:
        sections.append(_section("Due tomorrow", buckets["tomorrow"]))
    if not sections:
        body = "  <p>Nothing due today and nothing scheduled for tomorrow. Enjoy the day!</p>"
    else:
        body = "\n".join(f"  {section}" for section in sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title, quote=False)}</title>
  <style>
    body {{ font-family: Georgia, sans-serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem; color: #222; background: #fafafa; line-height: 1.5; }}
    h1, h2 {{ font-family: system-ui, sans-serif; }}
    table {{ border-collapse: separate; border-spacing: 0; width: 100%; background: #fff; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #eee; }}
    th {{ font-family: system-ui, sans-serif; background: #f0f0f0; }}
    .meta {{ color: #666; font-style: italic; font-size: 0.9rem; }}
  </style>
</head>
<body>
    <h1>{html.escape(title, quote=False)}</h1>
  <p class="meta">Generated {today.isoformat()}</p>
  {body}
</body>
</html>
"""
