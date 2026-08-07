from datetime import datetime, timedelta, timezone

from check_stale_channels import find_stale, format_report

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def row(**kw):
    base = {
        "channel_id": "1",
        "guild_name": "Test Guild",
        "channel_name": "reminders",
        "active": True,
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


def test_paused_channels_are_ignored():
    rows = [row(active=False, last_sent_at=(NOW - timedelta(days=10)).isoformat())]
    assert find_stale(rows, now=NOW) == []


def test_missing_active_key_defaults_to_active():
    r = row(last_sent_at=(NOW - timedelta(hours=40)).isoformat())
    del r["active"]
    assert len(find_stale([r], now=NOW)) == 1


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
