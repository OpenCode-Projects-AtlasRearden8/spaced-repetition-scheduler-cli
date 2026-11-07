"""SM-2 style scheduling engine.

Each card carries scheduling state (ease factor, interval, repetitions, due
date). Reviewing a card with a quality score from 0 to 5 advances (or resets)
its schedule exactly once; nothing here touches storage or the terminal.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

MIN_EASE_FACTOR = 1.3
DEFAULT_EASE_FACTOR = 2.5
FIRST_INTERVAL = 1
SECOND_INTERVAL = 6


def _today() -> date:
    return date.today()


def new_card(front: str, back: str, tag: str = "", today: date | None = None) -> dict:
    today = today or _today()
    return {
        "id": uuid.uuid4().hex,
        "front": front,
        "back": back,
        "tag": tag,
        "ease_factor": DEFAULT_EASE_FACTOR,
        "interval_days": 0,
        "repetitions": 0,
        "due": today.isoformat(),
        "history": [],
    }


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def interval_after(card: dict, quality: int) -> int:
    """Return the interval (in days) a review at ``quality`` would schedule."""
    reps = card["repetitions"]
    if quality < 3:
        return FIRST_INTERVAL
    if reps == 0:
        return FIRST_INTERVAL
    if reps == 1:
        return SECOND_INTERVAL
    gap = max(int(round(card["interval_days"] * card["ease_factor"])), card["interval_days"] + 1)
    return gap


def ease_factor_after(card: dict, quality: int) -> float:
    q = min(max(quality, 0), 5)
    slip = 5 - q
    ease = card["ease_factor"] + (0.1 - slip * (0.08 + slip * 0.02))
    return max(ease, MIN_EASE_FACTOR)


def apply_review(card: dict, quality: int, today: date | None = None) -> dict:
    """Apply one review to ``card`` in place and return it."""
    today = today or _today()
    if not 0 <= quality <= 5:
        raise ValueError(f"quality must be 0-5, got {quality!r}")

    interval = interval_after(card, quality)
    card["ease_factor"] = round(ease_factor_after(card, quality), 4)
    card["history"].append({"date": today.isoformat(), "quality": quality, "interval": interval})

    if quality < 3:
        card["repetitions"] = 0
    else:
        card["repetitions"] += 1
    card["interval_days"] = interval
    card["due"] = (today + timedelta(days=interval)).isoformat()
    return card


def is_due(card: dict, today: date | None = None) -> bool:
    return parse_date(card["due"]) <= (today or _today())


class QueueError(Exception):
    pass
