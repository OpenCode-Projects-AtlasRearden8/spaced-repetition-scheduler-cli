"""Local JSON storage and CSV import.

Everything is offline and local-first: the whole collection lives in a single
JSON file that the user controls (default ``~/.spaced-repetition-scheduler/cards.json``).
The path can be overridden with ``SRS_DATA`` or ``--data``.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Optional

from .scheduler import new_card

DEFAULT_DATA_FILE = Path.home() / ".spaced-repetition-scheduler" / "cards.json"

SCHEMA_VERSION = 1


class Store:
    """A thin wrapper around the JSON collection file."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or os.environ.get("SRS_DATA") or DEFAULT_DATA_FILE)

    @property
    def cards(self) -> list[dict]:
        return self.load()["cards"]

    def load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": SCHEMA_VERSION, "cards": []}
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("cards", [])
        return data

    def save(self, cards: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"schema_version": SCHEMA_VERSION, "cards": cards}, fh, indent=2, ensure_ascii=False)
        tmp.replace(self.path)


def normalize_fieldnames(reader: csv.DictReader) -> csv.DictReader:
    reader.fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
    return reader


def import_cards(cards: list[dict], csv_path: Path, default_tag: str = "", today=None) -> dict:
    """Import rows from ``csv_path`` into ``cards`` (in place) and return counts."""
    added, skipped = 0, 0
    seen_fronts = {card["front"].strip().casefold() for card in cards}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = normalize_fieldnames(csv.DictReader(fh))
        for row in reader:
            if row.get("\\ufefffront"):
                row["front"] = row.pop("\\ufefffront")
            front = (row.get("front") or "").strip()
            back = (row.get("back") or "").strip()
            tag = ((row.get("tag") or "").strip()) or default_tag
            if not front or not back:
                skipped += 1
                continue
            if front.casefold() in seen_fronts:
                skipped += 1
                continue
            cards.append(new_card(front, back, tag, today=today))
            seen_fronts.add(front.casefold())
            added += 1
    return {"added": added, "skipped": skipped}


def find_card(cards: list[dict], query: str) -> Optional[dict]:
    """Match a card by id, or by exact front text (case-insensitive)."""
    query = query.strip()
    matches = [card for card in cards if card["id"] == query]
    if not matches:
        matches = [card for card in cards if card["front"].strip().casefold() == query.casefold()]
    if len(matches) == 1:
        return matches[0]
    return None
