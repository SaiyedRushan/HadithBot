"""Post an update message (see updates/README.md) to every active channel.

    uv run python send_update.py                       # preview only: text, length, channels
    uv run python send_update.py --send --channel ID   # post to one channel
    uv run python send_update.py --send                # post to every active channel

The message is the newest updates/YYYY-MM-DD.md, or --file PATH (``-`` reads
stdin). On the VM the container has no .md files (.dockerignore drops them), so
the make targets pipe the file in over stdin instead.

Posts through Discord's REST API with whichever bot DISCORD_TOKEN belongs to:
the dev bot locally, the production bot on the VM.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# db is imported inside main(): it raises at import time without SUPABASE_URL,
# which would make the pure helpers below untestable without credentials.

UPDATES_DIR = Path(__file__).resolve().parent / "updates"
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
    parser.add_argument("--file", help="Message file to send (- for stdin). Default: newest in updates/")
    parser.add_argument("--channel", help="Only this channel id, to test before sending to everyone")
    parser.add_argument("--send", action="store_true", help="Actually post. Without it, only preview.")
    args = parser.parse_args()

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

    if args.channel:
        rows = [{"channel_id": args.channel}]
    else:
        from db import get_channels  # noqa: PLC0415 -- see note at the imports

        # Every channel, even several in one server: each was set up on its own.
        rows = get_channels()

    print(f"--- {source} ({len(text)}/{DISCORD_LIMIT} characters) ---")
    print(text)
    print(f"--- {len(rows)} channel(s) ---")
    for row in rows:
        print(f"  {channel_label(row)}")

    if not args.send:
        print("\nPreview only. Add --send to post it.")
        return 0

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN is not set.")
        return 1

    failed = 0
    for row in rows:
        error = post_message(token, str(row["channel_id"]), text)
        if error:
            failed += 1
            print(f"FAILED  {channel_label(row)}: {error}")
        else:
            print(f"sent    {channel_label(row)}")
        time.sleep(0.5)  # well under Discord's rate limits for ~20 channels

    print(f"\nSent to {len(rows) - failed} of {len(rows)} channel(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
