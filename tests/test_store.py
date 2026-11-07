"""Tests for JSON storage and CSV import."""

import csv
import json
from datetime import date

import pytest

from srs_scheduler.scheduler import new_card
from srs_scheduler.store import Store, find_card, import_cards

TODAY = date(2026, 11, 7)


def write_cards_csv(tmp_path, rows, extra_header=None, encoding="utf-8"):
    path = tmp_path / "cards.csv"
    with path.open("w", encoding=encoding, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=("front", "back", "tag"))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_import_adds_unique_cards(tmp_path):
    cards = []
    path = write_cards_csv(tmp_path, [
        {"front": "What is EF?", "back": "Ease factor", "tag": "sm2"},
        {"front": "Interval 1?", "back": "1 day", "tag": "sm2"},
    ])
    result = import_cards(cards, path, today=TODAY)
    assert result == {"added": 2, "skipped": 0}
    assert [card["front"] for card in cards] == ["What is EF?", "Interval 1?"]
    assert all(card["tag"] == "sm2" for card in cards)
    assert all(card["due"] == TODAY.isoformat() for card in cards)


def test_import_is_idempotent_on_front(tmp_path):
    cards = [new_card("What is EF?", "Ease factor", "old", today=TODAY)]
    path = write_cards_csv(tmp_path, [
        {"front": "What is EF?", "back": "different back", "tag": "new"},
        {"front": "case-insensitive", "back": "b", "tag": ""},
    ])
    result = import_cards(cards, path, today=TODAY)
    assert result["added"] == 1
    assert result["skipped"] == 1
    assert len(cards) == 2


def test_import_rows_without_front_or_back_are_skipped(tmp_path):
    cards = []
    path = write_cards_csv(tmp_path, [
        {"front": "ok", "back": "fine", "tag": ""},
        {"front": "", "back": "no front", "tag": ""},
        {"front": "no back", "back": "", "tag": ""},
    ])
    result = import_cards(cards, path, today=TODAY)
    assert result == {"added": 1, "skipped": 2}


def test_import_default_tag_fills_blank_tags(tmp_path):
    cards = []
    path = write_cards_csv(tmp_path, [{"front": "f", "back": "b", "tag": ""}])
    import_cards(cards, path, default_tag="defaulted", today=TODAY)
    assert cards[0]["tag"] == "defaulted"


def test_import_handles_utf8_bom(tmp_path):
    cards = []
    path = write_cards_csv(tmp_path, [{"front": "BOM front", "back": "b", "tag": "t"}], encoding="utf-8-sig")
    result = import_cards(cards, path, today=TODAY)
    assert result["added"] == 1
    assert cards[0]["front"] == "BOM front"


def test_store_round_trips_json(tmp_path):
    store = Store(tmp_path / "collection.json")
    cards = store.cards
    cards.append(new_card("persist", "me", tag="t", today=TODAY))
    store.save(cards)

    reloaded = Store(tmp_path / "collection.json")
    assert len(reloaded.cards) == 1
    assert reloaded.cards[0]["front"] == "persist"
    data = json.loads((tmp_path / "collection.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1


def test_find_card_by_front_and_id():
    card = new_card("unique front", "b", today=date(2026, 11, 6))
    other = new_card("another", "b", today=date(2026, 11, 6))
    assert find_card([card, other], "UNIQUE FRONT") is card
    assert find_card([card, other], card["id"]) is card
    assert find_card([card, other], "missing") is None
    assert find_card([card], "a") is None
