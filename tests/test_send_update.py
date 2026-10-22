"""Unit tests for the pure parts of send_update.py (no database, no Discord)."""

from send_update import check_message, latest_update


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
