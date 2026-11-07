"""Tests for queue bucket math and renderings."""

from datetime import date, timedelta

from srs_scheduler.queue import html_view, update_queue
from srs_scheduler.scheduler import new_card

TODAY = date(2026, 11, 7)


def setup_state(today=None):
    today = today or TODAY
    cards = [
        new_card("overdue", "b", "late", today=TODAY - timedelta(days=4)),
        new_card("due-today", "b", "now", today=TODAY),
        new_card("due-tomorrow", "b", "next", today=TODAY + timedelta(days=1)),
        new_card("due-later", "b", "later", today=TODAY + timedelta(days=9)),
    ]
    return cards


def test_buckets_land_in_the_right_list() -> None:
    buckets = update_queue(setup_state(), TODAY)
    assert [card["front"] for card in buckets["overdue"]] == ["overdue"]
    assert [card["front"] for card in buckets["today"]] == ["due-today"]
    assert [card["front"] for card in buckets["tomorrow"]] == ["due-tomorrow"]
    assert [card["front"] for card in buckets["later"]] == ["due-later"]


def test_overdue_is_sorted_oldest_first() -> None:
    cards = [
        new_card("newer", "b", tag="", today=TODAY - timedelta(days=2)),
        new_card("older", "b", tag="", today=TODAY - timedelta(days=5)),
    ]
    buckets = update_queue(cards, TODAY)
    assert [card["front"] for card in buckets["overdue"]] == ["older", "newer"]


def test_due_tomorrow_counts_as_one_day() -> None:
    due_tomorrow = new_card("c", "b", today=TODAY + timedelta(days=1))
    buckets = update_queue([due_tomorrow], TODAY)
    assert buckets["tomorrow"] and not buckets["today"]


def test_html_has_due_and_tomorrow_buckets() -> None:
    buckets = update_queue(setup_state(), TODAY)
    page = html_view(buckets, TODAY)
    assert "<!DOCTYPE html>" in page
    assert "<title>Today's Review Queue</title>" in page
    assert "Due today (2 card" in page
    assert "Due tomorrow (1 card)" in page
    assert "overdue" in page and "due-today" in page and "due-tomorrow" in page


def test_html_is_plain_and_offline() -> None:
    page = html_view(update_queue(setup_state(), TODAY), TODAY)
    stripped = page.casefold()
    assert "http://" not in stripped
    assert "https://" not in stripped
    assert "<script" not in stripped
    assert "<link" not in stripped


def test_html_escapes_card_text() -> None:
    card = new_card("<script>alert(1)</script>", "back", tag="", today=TODAY)
    page = html_view(update_queue([card], TODAY), TODAY)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_html_when_queue_is_empty() -> None:
    card = new_card("c", "b", today=TODAY + timedelta(days=3))
    page = html_view(update_queue([card], TODAY), TODAY)
    assert "Nothing due today and nothing scheduled for tomorrow" in page


def test_new_cards_are_due_on_import_day() -> None:
    cards = [new_card("fresh", "b", today=TODAY)]
    buckets = update_queue(cards, TODAY)
    assert buckets["today"] == cards
