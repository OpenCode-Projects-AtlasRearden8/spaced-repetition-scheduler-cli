"""Tests for the SM-2 style interval math."""

from datetime import date, timedelta

import pytest

from srs_scheduler.scheduler import (
    FIRST_INTERVAL,
    SECOND_INTERVAL,
    apply_review,
    ease_factor_after,
    interval_after,
    is_due,
    new_card,
)

TODAY = date(2026, 11, 7)
ONE_DAY = timedelta(days=1)
SIX_DAYS = timedelta(days=6)


def test_new_card_is_due_immediately() -> None:
    card = new_card("front", "back", "tag", today=TODAY)
    assert card["due"] == TODAY.isoformat()
    assert card["interval_days"] == 0
    assert card["repetitions"] == 0
    assert card["ease_factor"] == pytest.approx(2.5)
    assert is_due(card, today=TODAY)


def test_first_success_schedules_one_day() -> None:
    card = new_card("f", "b", today=TODAY)
    apply_review(card, 4, today=TODAY)
    assert card["interval_days"] == FIRST_INTERVAL
    assert card["repetitions"] == 1
    assert card["due"] == (TODAY + ONE_DAY).isoformat()


def test_second_success_schedules_six_days() -> None:
    card = new_card("f", "b", today=TODAY)
    apply_review(card, 4, today=TODAY)
    second = date(2026, 11, 8)
    apply_review(card, 4, today=second)
    assert card["interval_days"] == SECOND_INTERVAL
    assert card["due"] == (second + SIX_DAYS).isoformat()


def test_third_success_will_use_ease_factor() -> None:
    card = new_card("f", "b", today=TODAY)
    for _ in range(3):
        apply_review(card, 4, today=TODAY)
    assert card["interval_days"] == int(round(SECOND_INTERVAL * card["ease_factor"]))


def test_failure_resets_schedule_to_one_day() -> None:
    card = new_card("f", "b", today=TODAY)
    for _ in range(2):
        apply_review(card, 4, today=TODAY)
    apply_review(card, 2, today=TODAY)
    assert card["repetitions"] == 0
    assert card["interval_days"] == 1
    assert card["due"] == (TODAY + ONE_DAY).isoformat()


def test_interval_after_never_shrinks() -> None:
    card = new_card("f", "b", today=TODAY)
    card["interval_days"] = 42
    card["repetitions"] = 9
    card["ease_factor"] = 1.01
    assert interval_after(card, 4) > card["interval_days"]


def test_ease_factor_rises_for_easy_and_falls_for_fuzzy() -> None:
    card = new_card("f", "b", today=TODAY)
    assert ease_factor_after(card, 5) > 2.5
    assert ease_factor_after(card, 3) < 2.5


def test_ease_factor_never_falls_below_floor() -> None:
    card = new_card("f", "b", today=TODAY)
    card["ease_factor"] = 1.25
    assert ease_factor_after(card, 0) == pytest.approx(1.3)


def test_history_records_every_review() -> None:
    card = new_card("f", "b", today=TODAY)
    apply_review(card, 5, today=TODAY)
    apply_review(card, 3, today=TODAY)
    assert [entry["quality"] for entry in card["history"]] == [5, 3]
    assert [entry["date"] for entry in card["history"]] == [TODAY.isoformat()] * 2


@pytest.mark.parametrize("quality", [-1, 6, 99])
def test_invalid_quality_rejected(quality: int) -> None:
    card = new_card("f", "b", today=TODAY)
    with pytest.raises(ValueError):
        apply_review(card, quality, today=TODAY)
