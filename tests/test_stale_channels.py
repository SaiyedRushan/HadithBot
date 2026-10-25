from datetime import datetime, timedelta, timezone

from check_stale_channels import find_stale, format_report, split_stale

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def row(**kw):
    base = {
        "channel_id": "1",
        "guild_name": "Test Guild",
        "channel_name": "reminders",
        "last_sent_at": None,
        "created_at": (NOW - timedelta(days=30)).isoformat(),
    }
    base.update(kw)
    return base


def test_recent_delivery_is_not_stale():
    rows = [row(last_sent_at=(NOW - timedelta(hours=18)).isoformat())]
    assert find_stale(rows, now=NOW) == []


def test_delivery_older_than_window_is_stale():
    rows = [row(last_sent_at=(NOW - timedelta(hours=30)).isoformat())]
    stale = find_stale(rows, now=NOW)
    assert len(stale) == 1
    assert stale[0][1] is not None


def test_never_delivered_old_channel_is_stale():
    """The YorkU case: set up, never delivered to, silently broken."""
    stale = find_stale([row(last_sent_at=None)], now=NOW)
    assert len(stale) == 1
    assert stale[0][1] is None


def test_never_delivered_but_just_created_is_not_stale():
    """A channel set up an hour ago hasn't missed a send yet."""
    rows = [
        row(last_sent_at=None, created_at=(NOW - timedelta(hours=2)).isoformat())
    ]
    assert find_stale(rows, now=NOW) == []


def test_stopped_channels_are_ignored():
    """Removed from the server, deleted, or /bismillah stop: all the same here."""
    for reason in ("bot_removed", "channel_deleted", "stopped_by_admin"):
        rows = [
            row(
                last_sent_at=(NOW - timedelta(days=14)).isoformat(),
                stopped_at=(NOW - timedelta(days=13)).isoformat(),
                stopped_reason=reason,
            )
        ]
        assert find_stale(rows, now=NOW) == []


def test_a_channel_started_again_is_watched_again():
    """mark_guild_present and setup clear stopped_at, so it's checked again."""
    rows = [row(last_sent_at=(NOW - timedelta(days=14)).isoformat(), stopped_at=None)]
    assert len(find_stale(rows, now=NOW)) == 1


def test_unparseable_timestamp_treated_as_never_delivered():
    rows = [row(last_sent_at="not-a-date")]
    assert len(find_stale(rows, now=NOW)) == 1


def test_z_suffix_timestamp_parses():
    """Postgres/Supabase may hand back a trailing Z, which <3.11 can't parse."""
    ts = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    assert find_stale([row(last_sent_at=ts)], now=NOW) == []


def test_custom_window_is_respected():
    rows = [row(last_sent_at=(NOW - timedelta(hours=10)).isoformat())]
    assert find_stale(rows, stale_hours=26, now=NOW) == []
    assert len(find_stale(rows, stale_hours=8, now=NOW)) == 1


def test_report_names_the_channel_and_the_command():
    stale = find_stale([row(last_sent_at=None)], now=NOW)
    report = format_report(stale, now=NOW)
    assert "Test Guild" in report
    assert "reminders" in report
    assert "never delivered" in report
    assert "/bismillah diagnose" in report


def test_recently_stopped_channel_is_new():
    stale = find_stale(
        [row(last_sent_at=(NOW - timedelta(days=2)).isoformat())], now=NOW
    )
    new, old = split_stale(stale, now=NOW)
    assert len(new) == 1 and old == []


def test_long_stopped_channel_is_old():
    """The Ayo Ngaji case: a month without delivery, reported every day since."""
    stale = find_stale(
        [row(last_sent_at=(NOW - timedelta(days=30)).isoformat())], now=NOW
    )
    new, old = split_stale(stale, now=NOW)
    assert new == [] and len(old) == 1


def test_never_delivered_counts_from_setup():
    recent = row(
        channel_id="1",
        last_sent_at=None,
        created_at=(NOW - timedelta(days=2)).isoformat(),
    )
    long_ago = row(channel_id="2", last_sent_at=None)  # created 30 days ago
    new, old = split_stale(find_stale([recent, long_ago], now=NOW), now=NOW)
    assert [r["channel_id"] for r, _ in new] == ["1"]
    assert [r["channel_id"] for r, _ in old] == ["2"]


def test_no_timestamps_at_all_is_new():
    """Nothing to date it by, so fail rather than hide it."""
    stale = find_stale([row(last_sent_at=None, created_at=None)], now=NOW)
    new, old = split_stale(stale, now=NOW)
    assert len(new) == 1 and old == []


def test_report_lists_old_channels_separately():
    new = find_stale([row(channel_id="1", channel_name="fresh")], now=NOW)
    old = find_stale([row(channel_id="2", channel_name="ancient")], now=NOW)
    report = format_report(new, now=NOW, old=old)
    assert "1 channel(s) missed the daily hadith" in report
    assert "1 channel(s) still not delivering" in report
    assert report.index("fresh") < report.index("ancient")


def test_report_with_only_old_channels_has_no_missed_header():
    old = find_stale([row()], now=NOW)
    report = format_report([], now=NOW, old=old)
    assert "missed the daily hadith" not in report
    assert "still not delivering" in report
