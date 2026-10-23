"""Preview an update message, or post it to one channel to see it in Discord.

    uv run python send_update.py                              # preview the newest update
    uv run python send_update.py --send --channel ID          # post it to one channel

Updates are not sent from here. The daily broadcast posts updates/<date>.md in
every channel just before that day's hadith (see utils.update_for), so the
file's date is the day it goes out. See updates/README.md.

--file PATH picks a different file (``-`` reads stdin, which is how the make
target hands the file to the container on the VM). --send posts with whichever
bot DISCORD_TOKEN belongs to: the dev bot locally, the production bot on the VM.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from utils import UPDATES_DIR

# db is imported inside main(): it raises at import time without SUPABASE_URL,
# which would make the pure helpers below untestable without credentials.

DISCORD_LIMIT = 2000
API = "https://discord.com/api/v10"


def latest_update(directory: Path = UPDATES_DIR) -> Optional[Path]:
    """The newest dated update file, ignoring the README."""
    files = sorted(directory.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md"))
    return files[-1] if files else None


def check_message(text: str) -> Optional[str]:
    """Why this message can't be sent, or None if it can."""
    if not text.strip():
        return "The update message is empty."
    if len(text) > DISCORD_LIMIT:
        return (
            f"The update message is {len(text)} characters; Discord allows "
            f"{DISCORD_LIMIT}. Shorten it by {len(text) - DISCORD_LIMIT}."
        )
    return None


def when_it_goes_out(day: date, today: date) -> str:
    """Plain-English note on when the daily broadcast will post this file."""
    if day < today:
        return f"Dated {day}, which has passed. It won't be sent again."
    if day == today:
        return f"Goes out today ({day}) with the 6:00 PM Toronto message."
    return f"Goes out on {day} with the 6:00 PM Toronto message."


def channel_label(row: dict) -> str:
    guild = row.get("guild_name") or "unknown server"
    channel = row.get("channel_name") or row["channel_id"]
    return f"{guild} / #{channel}"


def post_message(token: str, channel_id: str, content: str) -> Optional[str]:
    """Send one message. Returns None on success, or what went wrong."""
    body = json.dumps(
        # No pings: an update should never @everyone or @role a server.
        {"content": content, "allowed_mentions": {"parse": []}}
    ).encode()
    for _ in range(3):
        req = urllib.request.Request(
            f"{API}/channels/{channel_id}/messages",
            data=body,
            headers={
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (https://github.com/SaiyedRushan/HadithBot, 1.0)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = json.loads(e.read() or b"{}").get("retry_after", 2)
                time.sleep(float(retry) + 0.5)
                continue
            return f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
        except urllib.error.URLError as e:
            return f"network error: {e.reason}"
    return "still rate limited after 3 tries"


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Message file (- for stdin). Default: newest in updates/")
    parser.add_argument("--channel", help="Channel id to post a test copy to (needs --send)")
    parser.add_argument("--send", action="store_true", help="Post the test copy to --channel")
    args = parser.parse_args()

    if args.send and not args.channel:
        print("--send needs --channel. Updates reach every channel through the daily message.")
        return 2

    path: Optional[Path] = None
    if args.file == "-":
        text, source = sys.stdin.read(), "stdin"
    else:
        path = Path(args.file) if args.file else latest_update()
        if path is None or not path.exists():
            print("No update file found. Write updates/YYYY-MM-DD.md or pass --file.")
            return 1
        text, source = path.read_text(), str(path)
    text = text.strip()

    problem = check_message(text)
    if problem:
        print(problem)
        return 1

    print(f"--- {source} ({len(text)}/{DISCORD_LIMIT} characters) ---")
    print(text)
    print("---")

    if args.send:
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            print("DISCORD_TOKEN is not set.")
            return 1
        error = post_message(token, args.channel, text)
        print(f"Couldn't post it: {error}" if error else f"Posted a test copy to {args.channel}.")
        return 1 if error else 0

    if path is not None:
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            day = None
        if day is not None:
            print(when_it_goes_out(day, datetime.now(ZoneInfo("America/Toronto")).date()))

    from db import get_channels  # noqa: PLC0415 -- see note at the imports

    rows = get_channels()
    print(f"It will be posted in {len(rows)} channel(s):")
    for row in rows:
        print(f"  {channel_label(row)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
