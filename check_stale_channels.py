"""Report active channels that haven't received their daily message.

A channel can break silently: the bot loses access, or was never granted it,
and send_daily_message logs the failure at 6pm and moves on. Nobody finds out
until someone in that server mentions it -- which is how a set-up channel went
a full day without its first hadith.

This compares last_sent_at against the schedule and reports anything overdue.
Run it after the daily send (see .github/workflows/stale-channel-check.yml).
Posts to DISCORD_ALERT_WEBHOOK when set; otherwise prints and exits non-zero,
which is enough to turn a scheduled CI run red.

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
        last_sent = _parse_ts(row.get("last_sent_at"))
        if last_sent is None:
            created = _parse_ts(row.get("created_at"))
            if created is not None and created > cutoff:
                continue
            stale.append((row, None))
        elif last_sent < cutoff:
            stale.append((row, last_sent))
    return stale


def format_report(stale, now=None):
    now = now or datetime.now(timezone.utc)
    lines = [f"**{len(stale)} channel(s) missed the daily hadith**"]
    for row, last_sent in stale:
        where = f"{row.get('guild_name') or '?'} / #{row.get('channel_name') or row['channel_id']}"
        if last_sent is None:
            when = "never delivered"
        else:
            when = f"last sent {int((now - last_sent).total_seconds() // 3600)}h ago"
        lines.append(f"• {where} — {when} (`{row['channel_id']}`)")
    lines.append(
        "\nRun `/bismillah diagnose` in the server to see what's blocking it."
    )
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
    active = sum(1 for r in rows if r.get("active", True))

    if not stale:
        print(f"All {active} active channel(s) delivered within {args.hours}h.")
        return 0

    report = format_report(stale)
    print(report)

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
