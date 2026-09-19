"""One-off backfill: populate channel_name / guild_id / guild_name /
guild_member_count for existing discord_channel_state rows by resolving each
stored channel_id against Discord.

Run once after adding the columns:  python backfill_channel_names.py
Safe to re-run; it only refreshes the label fields. Requires the bot to still be
a member of the servers whose channels are stored.
"""

import os
import asyncio
import discord
from dotenv import load_dotenv

from db import get_all_channels, save_channel_state

load_dotenv()


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set")

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            # on_ready can fire before every GUILD_CREATE has arrived, leaving the
            # channel cache incomplete. Give the gateway a moment to hydrate.
            await asyncio.sleep(8)
            rows = get_all_channels()
            print(f"Found {len(rows)} channel row(s) to backfill")
            for row in rows:
                cid = row["channel_id"]
                # get_channel uses the gateway cache (populated on ready); fall
                # back to a REST fetch for anything not cached.
                channel = client.get_channel(int(cid))
                if channel is None:
                    try:
                        channel = await client.fetch_channel(int(cid))
                    except (discord.NotFound, discord.Forbidden) as e:
                        print(f"  {cid}: channel not readable ({e})")
                        channel = None

                guild = getattr(channel, "guild", None)
                # A channel the bot can't read still sits in a server it can
                # see, and the member count comes from the server rather than
                # the channel -- so fall back to the stored guild_id instead of
                # dropping the row and leaving its members uncounted.
                if guild is None and row.get("guild_id"):
                    guild = client.get_guild(int(row["guild_id"]))
                if channel is None and guild is None:
                    print(f"  {cid}: no channel and no server to resolve; skipping")
                    continue

                save_channel_state(
                    cid,
                    row["last_hadith_no"],
                    row["last_name_no"],
                    row["last_book_id"],
                    row["last_chapter_id"],
                    channel_name=getattr(channel, "name", None),
                    guild_id=str(guild.id) if guild else None,
                    guild_name=guild.name if guild else None,
                    guild_member_count=guild.member_count if guild else None,
                )
                print(
                    f"  {cid}: channel_name={getattr(channel, 'name', None)!r} "
                    f"guild={(guild.name if guild else None)!r} "
                    f"guild_id={(guild.id if guild else None)} "
                    f"members={(guild.member_count if guild else None)}"
                )
        finally:
            await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
