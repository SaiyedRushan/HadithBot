"""Unit tests for the pure parts of send_update.py (no database, no Discord)."""

from datetime import date

from send_update import check_message, latest_update, when_it_goes_out
from utils import update_for


def test_latest_update_picks_newest_dated_file(tmp_path):
    for name in ("2026-01-05.md", "2026-10-22.md", "2026-03-01.md", "README.md"):
        (tmp_path / name).write_text("x")
    assert latest_update(tmp_path).name == "2026-10-22.md"


def test_latest_update_none_when_empty(tmp_path):
    (tmp_path / "README.md").write_text("x")
    assert latest_update(tmp_path) is None


def test_check_message_rejects_empty_and_too_long():
    assert check_message("   ") is not None
    assert "Shorten it by 1" in check_message("a" * 2001)
    assert check_message("a" * 2000) is None


def test_shipped_update_messages_fit_in_one_discord_message():
    from send_update import UPDATES_DIR

    for path in UPDATES_DIR.glob("[0-9]*.md"):
        assert check_message(path.read_text().strip()) is None, path.name


def test_update_for_finds_the_file_dated_that_day(tmp_path):
    (tmp_path / "2026-10-23.md").write_text("\n### Update\nhello\n")
    assert update_for(date(2026, 10, 23), tmp_path) == "### Update\nhello"
    assert update_for(date(2026, 10, 24), tmp_path) is None


def test_update_for_skips_messages_discord_would_reject(tmp_path):
    (tmp_path / "2026-10-23.md").write_text("a" * 2001)
    (tmp_path / "2026-10-24.md").write_text("   ")
    assert update_for(date(2026, 10, 23), tmp_path) is None
    assert update_for(date(2026, 10, 24), tmp_path) is None


def test_when_it_goes_out():
    today = date(2026, 10, 22)
    assert "has passed" in when_it_goes_out(date(2026, 10, 21), today)
    assert "today" in when_it_goes_out(today, today)
    assert "2026-10-23" in when_it_goes_out(date(2026, 10, 23), today)
