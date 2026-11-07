"""End-to-end CLI tests: import -> review via rate -> today/stats -> polish."""

import json
from datetime import date, timedelta

import pytest

from srs_scheduler.cli import main

TODAY = date(2026, 11, 7)
YESTERDAY = TODAY - timedelta(days=1)

CSV_ROWS = "front,back,tag\nPort 80?,HTTP,tcp\nTCP - handshake?,SYN/SYN-ACK/ACK,networking\n"


@pytest.fixture()
def env(monkeypatch, tmp_path):
    monkeypatch.delenv("SRS_DATA", raising=False)
    monkeypatch.delenv("SRS_LLM_MODEL", raising=False)
    monkeypatch.delenv("SRS_API_KEY", raising=False)
    data = tmp_path / "collection.json"
    csv_path = tmp_path / "cards.csv"
    csv_path.write_text(CSV_ROWS, encoding="utf-8")
    return data, csv_path


def test_full_flow_import_rate_today_stats(env, capsys):
    data, csv_path = env
    assert main(["--data", str(data), "import", str(csv_path)]) == 0
    assert main(["--data", str(data), "rate", "Port 80?", "4", "--date", str(YESTERDAY)]) == 0
    out = capsys.readouterr().out
    assert "next due 2026-11-07" in out

    main(["--data", str(data), "rate", "TCP - handshake?", "3", "--date", str(TODAY)])
    today_out = capsys.readouterr().out
    assert "next due 2026-11-08" in today_out

    assert main(["--data", str(data), "today", "--today-date", str(TODAY)]) == 0
    today_out = capsys.readouterr().out
    assert "1 card(s) due" in today_out
    assert "Port 80?" in today_out
    assert "TCP - handshake?" not in today_out.split("Due tomorrow")[0]

    today_html = data.parent / "queue.html"
    assert main(["--data", str(data), "today", "--html", str(today_html), "--today-date", str(TODAY)]) == 0
    page = today_html.read_text(encoding="utf-8")
    assert "Due today" in page and "Port 80?" in page

    assert main(["--data", str(data), "stats"]) == 0
    stats_out = capsys.readouterr().out
    assert "Cards: 2" in stats_out
    assert "Due today (incl. overdue): 1" in stats_out
    assert "Due tomorrow: 1" in stats_out
    assert "Reviews recorded: 2" in stats_out


def test_rate_rejects_bad_quality(env):
    data, csv_path = env
    main(["--data", str(data), "import", str(csv_path)])
    with pytest.raises(SystemExit):
        main(["--data", str(data), "rate", "Port 80?", "9"])


def test_rate_calls_review_math_for_ease_floor(env, capsys):
    data, csv_path = env
    main(["--data", str(data), "import", str(csv_path)])
    for quality in ("3", "3", "3"):
        main(["--data", str(data), "rate", "Port 80?", quality, "--date", str(TODAY)])
    cards = json.loads(data.read_text(encoding="utf-8"))["cards"]
    card = next(card for card in cards if card["front"] == "Port 80?")
    assert card["ease_factor"] >= 1.3


def test_review_rates_and_skips(env, monkeypatch, capsys):
    import builtins

    data, csv_path = env
    main(["--data", str(data), "import", str(csv_path)])
    answers = iter(["", "5", "", "1"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers, "q"))
    assert main(["--data", str(data), "review"]) == 0
    out = capsys.readouterr().out
    assert "2 card(s) due" in out
    assert "Finished: 2 card(s) rated" in out
    cards = json.loads(data.read_text(encoding="utf-8"))["cards"]
    assert {card["repetitions"] for card in cards} == {0, 1}


def test_review_with_empty_collection(env, capsys):
    data, _ = env
    assert main(["--data", str(data), "review"]) == 0
    assert "Nothing due right now" in capsys.readouterr().out


def test_polish_errors_without_model(env, capsys):
    data, _ = env
    assert main(["--data", str(data), "polish", "--limit", "1"]) == 1
    assert "no model given" in capsys.readouterr().err


def test_deprecated_import_json_roundtrip(env):
    data, csv_path = env
    main(["--data", str(data), "import", str(csv_path)])
    collection = json.loads(data.read_text(encoding="utf-8"))
    assert collection["schema_version"] == 1
    assert len(collection["cards"]) == 2
