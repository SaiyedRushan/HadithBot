"""Report active channels that haven't received their daily message.

A channel can break silently: the bot loses access, or was never granted it,
and send_daily_message logs the failure at 6pm and moves on. Nobody finds out
until someone in that server mentions it -- which is how a set-up channel went
a full day without its first hadith.

This compares last_sent_at against the schedule and reports anything overdue.
Run it after the daily send (see .github/workflows/stale-channel-check.yml).
Posts to DISCORD_ALERT_WEBHOOK when set; otherwise prints and exits non-zero,
which is enough to turn a scheduled CI run red. Channels that stopped more than
REPORTED_AFTER_DAYS ago are still listed but don't fail the run.

    uv run python check_stale_channels.py [--hours 26]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

# db is imported inside main(): it raises at import time when SUPABASE_URL is
# unset, which would make find_stale/format_report untestable without live
# credentials. The logic below is pure and needs no database.

# The send runs once a day, so anything past ~1 day is overdue. The default
# allows a little over a full cycle so a late run, or a check that fires
# slightly early, doesn't read as a failure.
DEFAULT_STALE_HOURS = 26

# A channel that has been failing this long was already reported on earlier
# runs, and the bot has DMed the owner about it. It stays in the report but no
# longer fails the run: a server that revoked our permissions and never fixed
# them would otherwise keep the check red every day, and a channel that breaks
# tomorrow would be lost in it. With the check at 12:00 UTC and the send at
# 22:00 UTC, 4 days means a newly broken channel fails 3 mornings in a row.
REPORTED_AFTER_DAYS = 4


def _parse_ts(value):
    """Postgres timestamptz -> aware datetime, or None if unset/unparseable."""
    if not value:
        return None
    try:
        # Python <3.11 can't parse a trailing 'Z'.
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def find_stale(rows, stale_hours=DEFAULT_STALE_HOURS, now=None):
    """Active channels whose last delivery is older than stale_hours.

    Channels that have never been delivered to (last_sent_at null) are only
    reported once they have existed longer than the window -- a channel set up
    an hour ago hasn't missed anything yet.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=stale_hours)
    stale = []
    for row in rows:
        if not row.get("active", True):
            continue
        # The bot isn't in this server any more, so of course nothing was
        # delivered. Reporting it every day would train you to ignore the
        # alert, which is the one thing it can't afford.
        if row.get("removed_at"):
            continue
        last_sent = _parse_ts(row.get("last_sent_at"))
        if last_sent is None:
            created = _parse_ts(row.get("created_at"))
            if created is not None and created > cutoff:
                continue
            stale.append((row, None))
        elif last_sent < cutoff:
            stale.append((row, last_sent))
    return stale


def split_stale(stale, reported_after_days=REPORTED_AFTER_DAYS, now=None):
    """(new, old): channels that stopped recently, and ones already reported.

    A never-delivered channel counts from when it was set up. One with no
    usable timestamp at all is treated as new, so it fails rather than hides.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=reported_after_days)
    new, old = [], []
    for row, last_sent in stale:
        since = last_sent or _parse_ts(row.get("created_at"))
        if since is not None and since < cutoff:
            old.append((row, last_sent))
        else:
            new.append((row, last_sent))
    return new, old


def _report_line(row, last_sent, now):
    where = f"{row.get('guild_name') or '?'} / #{row.get('channel_name') or row['channel_id']}"
    if last_sent is None:
        when = "never delivered"
    else:
        when = f"last sent {int((now - last_sent).total_seconds() // 3600)}h ago"
    return f"• {where}: {when} (`{row['channel_id']}`)"


def format_report(stale, now=None, old=()):
    now = now or datetime.now(timezone.utc)
    lines = []
    if stale:
        lines.append(f"**{len(stale)} channel(s) missed the daily hadith**")
        lines.extend(_report_line(row, last_sent, now) for row, last_sent in stale)
        lines.append(
            "\nRun `/bismillah diagnose` in the server to see what's blocking it."
        )
    if old:
        if lines:
            lines.append("")
        lines.append(
            f"**{len(old)} channel(s) still not delivering**, stopped more than "
            f"{REPORTED_AFTER_DAYS} days ago and already reported. "
            "These don't fail the check."
        )
        lines.extend(_report_line(row, last_sent, now) for row, last_sent in old)
    return "\n".join(lines)


def post_to_discord(webhook_url, content):
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"content": content}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


def main():
    load_dotenv()
    from db import get_all_channels  # noqa: PLC0415 -- see note at the imports

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours",
        type=int,
        default=DEFAULT_STALE_HOURS,
        help=f"How many hours without a delivery counts as stale (default {DEFAULT_STALE_HOURS})",
    )
    args = parser.parse_args()

    rows = get_all_channels()
    stale = find_stale(rows, stale_hours=args.hours)
    active = sum(
        1 for r in rows if r.get("active", True) and not r.get("removed_at")
    )
    removed = sum(1 for r in rows if r.get("removed_at"))
    removed_note = (
        f" ({removed} channel(s) skipped: the bot is no longer in those servers.)"
        if removed
        else ""
    )

    if not stale:
        print(
            f"All {active} active channel(s) delivered within {args.hours}h."
            f"{removed_note}"
        )
        return 0

    new, old = split_stale(stale)
    report = format_report(new, old=old)
    print(report)

    if not new:
        # Only channels that were reported on earlier runs. Listed above for
        # the run summary, but not posted again and not a failure.
        return 0

    webhook = os.environ.get("DISCORD_ALERT_WEBHOOK")
    if webhook:
        try:
            post_to_discord(webhook, report)
            print("\nPosted to the alert webhook.")
            # Alerting succeeded, so the run itself is healthy -- the report is
            # the output, not a CI failure.
            return 0
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"\nFailed to post to the alert webhook: {e}", file=sys.stderr)
            return 1

    # No webhook configured: exit non-zero so a scheduled run goes red.
    return 1


if __name__ == "__main__":
    sys.exit(main())
