from datetime import time
import aiofiles
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import json
import random
import logging
from typing import List, Optional
from zoneinfo import ZoneInfo
from db import (
    find_valid_hadith_position,
    get_all_channels,
    get_books,
    get_chapters,
    get_channels,
    get_channel_state,
    get_hadith_in_same_chapter_and_book,
    get_flags_for_hadith,
    get_next_hadiths,
    get_open_flags,
    get_random_hadith,
    remove_channel_state,
    resolve_hadith_flags,
    save_channel_state,
)
from views import FlagHadithButton, build_hadith_view
from utils import (
    Name,
    compose_flag_reply,
    getHadithFormattedMessage,
    getNameFormattedMessage,
    resolve_start_position,
)

# Tail of the /bismillah books and /bismillah chapters replies. Both lists run
# to several messages in Discord and can't be searched; the page holds the same
# ids in one place, with the hadith counts and number ranges alongside them.
BOOKS_PAGE_HINT = "\n-# The full list, searchable, is at <https://hadithbot.app/books>"


class HadithBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.names: List[Name] = []
        self.logger = logging.getLogger("HadithBot")

        # Setup error handling
        self.setup_error_handlers()

    async def setup_hook(self):
        """Initialize bot data and sync commands"""
        await self.load_data()
        # Registered before anything is sent so flag clicks on messages from a
        # previous run are still routed to a handler after a restart.
        self.add_dynamic_items(FlagHadithButton)
        await self.tree.sync()
        self.send_daily_message.start()

    async def load_data(self):
        """Load messages and names from local storage"""
        try:
            # Read and parse 99names.json
            async with aiofiles.open("data/99names.json", mode="r") as file:
                names_data = json.loads(await file.read())
                self.names = [Name(**name) for name in names_data]

        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            raise

    def setup_error_handlers(self):
        @self.event
        async def on_error(event, *args, **kwargs):
            self.logger.error(f"Error in {event}", exc_info=True)

        @self.tree.error
        async def on_command_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ):
            if isinstance(error, app_commands.CommandOnCooldown):
                message = f"Please wait {error.retry_after:.2f} seconds before using this command again."
            elif isinstance(error, app_commands.MissingPermissions):
                message = (
                    "You need the **Manage Channels** permission to use this command."
                )
            elif isinstance(getattr(error, "original", None), discord.Forbidden):
                message = (
                    "I don't have permission to post in this channel. "
                    "Please grant me **View Channel** and **Send Messages** here."
                )
            else:
                self.logger.error(f"Command error: {error}", exc_info=True)
                message = "An error occurred while processing your command. Please try again later."

            # Commands defer() before doing work, so the interaction is usually
            # already responded to by the time an error reaches here -- use
            # followup.send() in that case to avoid InteractionResponded.
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    await interaction.response.send_message(message, ephemeral=True)
            except discord.HTTPException:
                self.logger.error(
                    "Failed to deliver error message to user", exc_info=True
                )

    @tasks.loop(time=time(hour=18, tzinfo=ZoneInfo("America/Toronto")))
    async def send_daily_message(self):
        """Loops through the active channels and sends daily messages"""
        await self.run_daily_broadcast()

    async def run_daily_broadcast(self, only_channel_id: Optional[str] = None) -> int:
        """The daily broadcast itself, callable outside the 6pm schedule.

        Split out of send_daily_message so /bismillah send-now exercises this
        exact code path rather than a copy that can drift from it. Returns the
        number of channels delivered to; only_channel_id restricts it to one,
        which is what the command uses so a test can't spam every server."""
        try:
            channels = get_channels()
        except Exception as e:
            self.logger.error(f"Failed to fetch active channels: {e}")
            return 0

        if only_channel_id is not None:
            channels = [
                c for c in channels if str(c["channel_id"]) == str(only_channel_id)
            ]

        delivered = 0
        for channel_row in channels:
            channel_id = channel_row["channel_id"]
            # Isolate each channel so one failure (e.g. missing permissions)
            # doesn't stop the broadcast to the remaining channels.
            try:
                last_hadith_no = channel_row["last_hadith_no"]
                last_name_no = channel_row["last_name_no"]
                last_book_no = channel_row["last_book_id"]
                last_chapter_no = channel_row["last_chapter_id"]
                # Per-channel daily counts (default 3 for rows set before this was configurable)
                hadiths_per_day = channel_row.get("hadiths_per_day", 3)
                names_per_day = channel_row.get("names_per_day", 3)

                channel = self.get_channel(int(channel_id))
                if not channel:
                    self.logger.error(f"Channel {channel_id} not found")
                    continue

                # The book/chapter we resumed from (before position resolution).
                # Used to detect when today's batch moves into a new book/chapter
                # -- including a day-boundary roll-over -- so we can announce it.
                prev_book_no = last_book_no
                prev_chapter_no = last_chapter_no

                last_hadith_no, last_book_no, last_chapter_no = (
                    find_valid_hadith_position(
                        last_hadith_no, last_book_no, last_chapter_no
                    )
                )

                # send greeting
                await channel.send(
                    "> # Assalamu Alaikum Warahmatullahi Wabarakatuh, here is today's hadith and one of Allah's beautiful name\n"
                )
                # get name and send message
                names = self.get_names(last_name_no, names_per_day)
                current_name_index = self.get_next_index(
                    last_name_no, len(self.names), names_per_day
                )
                await self.send_formatted_name(channel, names)

                # get today's batch starting at the current position; this crosses
                # chapter/book boundaries so the full daily count is sent even when
                # the current chapter has fewer hadiths left than hadiths_per_day
                hadith = get_next_hadiths(
                    last_hadith_no, last_book_no, last_chapter_no, hadiths_per_day
                )

                if hadith:
                    for h in hadith:
                        # Announce whenever a hadith opens a book/chapter different
                        # from the previous one sent (a new book implies a new
                        # chapter, so only send one banner).
                        if h["book_id"] != prev_book_no:
                            await self.send_new_book_message(channel, h)
                        elif h["chapter_id"] != prev_chapter_no:
                            await self.send_new_chapter_message(channel, h)
                        prev_book_no = h["book_id"]
                        prev_chapter_no = h["chapter_id"]

                        await self.send_formatted_hadith(channel, h)

                    # The last hadith sent may be in a later chapter/book than we
                    # started; advance the saved position past it so tomorrow
                    # continues from the right spot.
                    last = hadith[-1]
                    last_book_no = last["book_id"]
                    last_chapter_no = last["chapter_id"]
                    next_hadith_no = last["id_in_book"] + 1

                    guild = getattr(channel, "guild", None)
                    save_channel_state(
                        channel_id,
                        next_hadith_no,
                        current_name_index,
                        last_book_no,
                        last_chapter_no,
                        channel_name=getattr(channel, "name", None),
                        guild_id=str(guild.id) if guild else None,
                        guild_name=guild.name if guild else None,
                        mark_sent=True,
                    )

                    delivered += 1
                    self.logger.info(
                        f"Successfully sent hadith up to book {last_book_no}, chapter {last_chapter_no}, hadith {last['id_in_book']}"
                    )
                else:
                    self.logger.error(
                        f"No hadith data returned for book {last_book_no}, chapter {last_chapter_no}, hadith {last_hadith_no}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to send daily message to channel {channel_id}: {e}",
                    exc_info=True,
                )
        return delivered

    @send_daily_message.before_loop
    async def before_daily_message(self):
        """Wait for the bot to be ready before starting the task"""
        await self.wait_until_ready()
        self.logger.info("\nDaily message task is ready to start\n")

    def get_names(self, number: int, count: int = 1) -> Optional[List[Name]]:
        """Get name by number with validation"""
        if 1 <= number <= len(self.names):
            return self.names[number - 1 : number + count - 1]
        return None

    @staticmethod
    def get_next_index(current: int, max_value: int, increment: int = 1) -> int:
        """Get next index with wraparound"""
        return (current + increment) if (current + increment < max_value) else 1

    async def send_new_book_message(self, channel: discord.TextChannel, hadith: dict):
        """Announce that the daily readings have moved into a new book."""
        book = (hadith.get("books_metadata") or {}).get("english_title") or "a new book"
        chapter = (hadith.get("chapters") or {}).get("english") or ""
        message = f"> # 📖 We are now starting a new book: {book}\n"
        if chapter:
            message += f"> ### Beginning with Chapter: {chapter}\n"
        await channel.send(message)

    async def send_new_chapter_message(
        self, channel: discord.TextChannel, hadith: dict
    ):
        """Announce that the daily readings have moved into a new chapter."""
        chapter = (hadith.get("chapters") or {}).get("english") or "a new chapter"
        await channel.send(f"> # 📖 We are now starting a new chapter: {chapter}\n")

    async def send_formatted_hadith(self, channel: discord.TextChannel, hadith: dict):
        """Send formatted hadith message"""
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        # Attach the link button to the last chunk so it sits under the full hadith.
        view = build_hadith_view(hadith)
        last_index = len(formatted_messages) - 1
        for i, message in enumerate(formatted_messages):
            if i == last_index and view is not None:
                await channel.send(message, view=view)
            else:
                await channel.send(message)

    async def send_formatted_name(
        self, channel: discord.TextChannel, names: List[Name]
    ):
        """Send formatted name messages for multiple names"""
        if not names:
            return
        for name in names:
            formatted_message = getNameFormattedMessage(name)
            await channel.send(formatted_message)

    async def reply_formatted_hadith(
        self, interaction: discord.Interaction, hadith: dict
    ):
        """Send a hadith privately (ephemeral) to the command invoker.

        The interaction must already be deferred with ephemeral=True.
        """
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        # Attach the link button to the last chunk so it sits under the full hadith.
        view = build_hadith_view(hadith)
        last_index = len(formatted_messages) - 1
        for i, message in enumerate(formatted_messages):
            if i == last_index and view is not None:
                await interaction.followup.send(message, view=view, ephemeral=True)
            else:
                await interaction.followup.send(message, ephemeral=True)

    async def reply_formatted_name(
        self, interaction: discord.Interaction, names: List[Name]
    ):
        """Send name(s) privately (ephemeral) to the command invoker.

        The interaction must already be deferred with ephemeral=True.
        """
        if not names:
            return
        for name in names:
            await interaction.followup.send(
                getNameFormattedMessage(name), ephemeral=True
            )


# Command group for better organization
@app_commands.guild_only()
class HadithCommands(app_commands.Group):
    def __init__(self, bot: HadithBot):
        super().__init__(name="bismillah")
        self.bot = bot

    @app_commands.command(name="random")
    async def random(self, interaction: discord.Interaction):
        # Ephemeral so the result is visible only to the member who ran it.
        await interaction.response.defer(ephemeral=True)
        hadith = get_random_hadith()
        if not hadith:
            await interaction.followup.send(
                "Couldn't fetch a hadith right now. Please try again.",
                ephemeral=True,
            )
            return
        await self.bot.reply_formatted_hadith(interaction, hadith)

    @app_commands.command(name="specific")
    @app_commands.describe(book_no="The book id of the hadith")
    @app_commands.describe(chapter_no="The chapter id of the hadith")
    @app_commands.describe(hadith_no="The hadith id of the hadith")
    async def specific(
        self,
        interaction: discord.Interaction,
        book_no: int,
        chapter_no: int,
        hadith_no: int,
    ):
        await interaction.response.defer(ephemeral=True)
        hadith = get_hadith_in_same_chapter_and_book(hadith_no, book_no, chapter_no)
        if not hadith:
            await interaction.followup.send(
                "No hadith found for that book, chapter, and hadith combination.",
                ephemeral=True,
            )
            return
        await self.bot.reply_formatted_hadith(interaction, hadith[0])

    async def _send_names(
        self,
        interaction: discord.Interaction,
        names: Optional[List[Name]],
    ):
        """Validate the requested names, then send them privately to the invoker."""
        await interaction.response.defer(ephemeral=True)
        if not names:
            await interaction.followup.send(
                f"Invalid name number. Please choose between 1 and {len(self.bot.names)}",
                ephemeral=True,
            )
            return
        await self.bot.reply_formatted_name(interaction, names)

    @app_commands.command(name="random_name")
    async def random_name(self, interaction: discord.Interaction):
        names = self.bot.get_names(random.randint(1, len(self.bot.names)), 1)
        await self._send_names(interaction, names)

    @app_commands.command(name="specific_names")
    @app_commands.describe(number="The starting number of the names")
    async def specific_names(self, interaction: discord.Interaction, number: int):
        names = self.bot.get_names(number, 3)
        await self._send_names(interaction, names)

    @app_commands.command(name="specific_name")
    @app_commands.describe(number="The number of the name")
    async def specific_name(self, interaction: discord.Interaction, number: int):
        names = self.bot.get_names(number, 1)
        await self._send_names(interaction, names)

    @app_commands.command(name="setup")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to send daily messages to (defaults to this channel)",
        hadiths_per_day="How many hadiths to send each day, 1-10 (default 3; kept if blank)",
        names_per_day="How many of Allah's names to send each day, 1-10 (default 3; kept if blank)",
        start_book_id="Book id to start from — see /bismillah books (blank keeps current, or starts at the beginning)",
        start_chapter_id="Chapter id to start from — see /bismillah chapters (blank keeps current)",
        start_hadith_id="Hadith id to start from (blank uses the chapter's first hadith, or keeps current)",
        start_name="Name number to start from (blank keeps current)",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        hadiths_per_day: Optional[int] = None,
        names_per_day: Optional[int] = None,
        start_book_id: Optional[int] = None,
        start_chapter_id: Optional[int] = None,
        start_hadith_id: Optional[int] = None,
        start_name: Optional[int] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return

        # Interaction replies use the interaction token, not channel permissions,
        # so setup can otherwise report success for a channel the bot can never
        # post in -- the failure only shows up as a missing message at 6pm.
        # Check up front and tell the admin while they're still here to fix it.
        me = target.guild.me
        if me is not None:
            perms = target.permissions_for(me)
            missing = [
                name
                for name, ok in (
                    ("View Channel", perms.view_channel),
                    ("Send Messages", perms.send_messages),
                )
                if not ok
            ]
            if missing:
                await interaction.followup.send(
                    f"I can't post in {target.mention} — missing "
                    f"{', '.join(f'**{m}**' for m in missing)}.\n"
                    "Grant those in the channel's permission settings and run "
                    "`/bismillah setup` again. Nothing has been saved.",
                    ephemeral=True,
                )
                return

        # Re-running setup edits the existing config. Any field left blank keeps
        # its current value (or falls back to a default for a brand-new channel),
        # so changing the daily counts no longer resets a channel's progress.
        existing = get_channel_state(str(target.id))

        def pick(value, key, default):
            if value is not None:
                return value
            if existing is not None:
                return existing.get(key, default)
            return default

        hpd = pick(hadiths_per_day, "hadiths_per_day", 3)
        npd = pick(names_per_day, "names_per_day", 3)
        if not (1 <= hpd <= 10) or not (1 <= npd <= 10):
            await interaction.followup.send(
                "Please choose between 1 and 10 for the per-day counts.",
                ephemeral=True,
            )
            return

        # Book/chapter/hadith are resolved together so that changing the book or
        # chapter (without naming a hadith) starts at that chapter's first hadith
        # instead of keeping the stale number. See resolve_start_position.
        last_book, last_chapter, last_hadith = resolve_start_position(
            existing, start_book_id, start_chapter_id, start_hadith_id
        )
        save_channel_state(
            str(target.id),
            last_hadith,
            pick(start_name, "last_name_no", 1),
            last_book,
            last_chapter,
            active=True,
            hadiths_per_day=hpd,
            names_per_day=npd,
            channel_name=target.name,
            guild_id=str(target.guild.id),
            guild_name=target.guild.name,
        )
        verb = "updated for" if existing else "set up for"
        await interaction.followup.send(
            f"Daily messages {verb} {target.mention} — "
            f"{hpd} hadith and {npd} name(s) per day.",
            ephemeral=True,
        )

    @app_commands.command(name="stop")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to stop sending messages to (defaults to this channel)"
    )
    async def stop(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return
        remove_channel_state(str(target.id))
        await interaction.followup.send(
            f"Daily messages will no longer be sent to {target.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="status")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def status(self, interaction: discord.Interaction):
        """Show which channels in this server have daily messages set up."""
        await interaction.response.defer(ephemeral=True)
        try:
            rows = get_all_channels()
        except Exception:
            self.bot.logger.error("Failed to fetch channel states", exc_info=True)
            await interaction.followup.send(
                "Couldn't fetch the channel status right now. Please try again later.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        lines: List[str] = []
        for row in rows:
            # Resolve against this guild so only channels in *this* server show.
            # A channel from another server (or a deleted one) won't resolve here.
            channel = guild.get_channel(int(row["channel_id"])) if guild else None
            if channel is None:
                continue
            state = "🟢 active" if row.get("active", True) else "⏸️ paused"
            lines.append(
                f"{channel.mention} — {state} — "
                f"{row.get('hadiths_per_day', 3)} hadith/{row.get('names_per_day', 3)} name(s) per day "
                f"(next: book {row['last_book_id']}, chapter {row['last_chapter_id']}, "
                f"hadith {row['last_hadith_no']}, name #{row['last_name_no']})"
            )

        if not lines:
            await interaction.followup.send(
                "No channels are set up in this server yet. "
                "Use `/bismillah setup` to start daily messages in a channel.",
                ephemeral=True,
            )
            return

        await self._send_reference(
            interaction,
            f"**Daily message channels here** ({len(lines)} configured) — "
            "sent daily at 6:00 PM Toronto time:",
            lines,
        )

    @app_commands.command(name="diagnose")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        send_test="Actually post a test message to each channel (default: check only)"
    )
    async def diagnose(
        self, interaction: discord.Interaction, send_test: Optional[bool] = False
    ):
        """Check why the daily message may not be arriving in a channel.

        Walks the same path send_daily_message does -- cache lookup, then
        permissions -- and reports where it breaks, instead of failing silently
        at 6pm. With send_test, it also attempts a real post so Discord's own
        error (not our guess at it) is surfaced."""
        await interaction.response.defer(ephemeral=True)
        try:
            rows = get_all_channels()
        except Exception:
            self.bot.logger.error("Failed to fetch channel states", exc_info=True)
            await interaction.followup.send(
                "Couldn't fetch the channel status right now. Please try again later.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Run this inside a server.", ephemeral=True)
            return

        # Only rows belonging to this guild. Match on the stored guild_id rather
        # than resolving the channel, because an unresolvable channel is exactly
        # the failure we're here to report -- filtering on it would hide it.
        mine = [r for r in rows if str(r.get("guild_id")) == str(guild.id)]
        if not mine:
            await interaction.followup.send(
                "No channels are set up in this server yet. "
                "Use `/bismillah setup` to start daily messages in a channel.",
                ephemeral=True,
            )
            return

        lines: List[str] = []
        for row in mine:
            channel_id = row["channel_id"]
            label = row.get("channel_name") or channel_id
            if not row.get("active", True):
                lines.append(f"⏸️ **{label}** — paused, no daily message by design.")
                continue

            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                lines.append(
                    f"❌ **{label}** (`{channel_id}`) — the bot cannot see this channel. "
                    "Either it was added to your account instead of the server "
                    "(re-invite it with the **bot** scope), it was removed, or it "
                    "lacks **View Channel** here."
                )
                continue

            perms = channel.permissions_for(guild.me)
            missing = [
                name
                for name, ok in (
                    ("View Channel", perms.view_channel),
                    ("Send Messages", perms.send_messages),
                )
                if not ok
            ]
            if missing:
                lines.append(
                    f"❌ {channel.mention} — missing {', '.join(f'**{m}**' for m in missing)}."
                )
                continue

            if not send_test:
                lines.append(f"✅ {channel.mention} — looks deliverable.")
                continue

            try:
                await channel.send(
                    "> 🧪 HadithBot test message — daily delivery to this channel is working."
                )
                lines.append(f"✅ {channel.mention} — test message sent.")
            except discord.HTTPException as e:
                # The real reason, straight from Discord, rather than our inference.
                lines.append(f"❌ {channel.mention} — send failed: `{e.text or e}`")
                self.bot.logger.error(
                    f"Diagnose test send failed for channel {channel_id}: {e}",
                    exc_info=True,
                )

        await self._send_reference(
            interaction,
            f"**Delivery check** ({len(mine)} configured):",
            lines,
        )

    @app_commands.command(name="send-now")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to send to (defaults to this channel)",
    )
    async def send_now(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Send this channel's daily message right now, without waiting for 6pm.

        Runs the real broadcast for one channel, so what you see is what 6pm
        would have produced. That means it genuinely advances the reading
        position -- it is a real delivery, not a preview."""
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return

        if get_channel_state(str(target.id)) is None:
            await interaction.followup.send(
                f"{target.mention} isn't set up yet — run `/bismillah setup` there first.",
                ephemeral=True,
            )
            return

        delivered = await self.bot.run_daily_broadcast(only_channel_id=str(target.id))
        if delivered:
            await interaction.followup.send(
                f"Sent today's message to {target.mention}. Its place has moved "
                "forward, so tomorrow continues from after this one.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Nothing was sent to {target.mention}. It may be paused — run "
                "`/bismillah diagnose` to see what's blocking it.",
                ephemeral=True,
            )

    async def _send_reference(
        self, interaction: discord.Interaction, header: str, lines: List[str]
    ):
        """Send a header + list as one or more ephemeral followups, each within
        Discord's 2000-character message limit."""
        chunk = header
        for line in lines:
            if len(chunk) + len(line) + 1 > 1900:
                await interaction.followup.send(chunk, ephemeral=True)
                chunk = ""
            chunk = f"{chunk}\n{line}" if chunk else line
        if chunk:
            await interaction.followup.send(chunk, ephemeral=True)

    @app_commands.command(name="books")
    async def books(self, interaction: discord.Interaction):
        """List all books and their ids (for use with /bismillah setup)."""
        await interaction.response.defer(ephemeral=True)
        lines = [f"`{b['id']}` — {b['english_title']}" for b in get_books()]
        lines.append(BOOKS_PAGE_HINT)
        await self._send_reference(
            interaction,
            "**Books** — use the number as `start_book_id` in `/bismillah setup`:",
            lines,
        )

    @app_commands.command(name="chapters")
    @app_commands.describe(book="Book id (see /bismillah books)")
    async def chapters(self, interaction: discord.Interaction, book: int):
        """List the chapters and their ids in a book."""
        await interaction.response.defer(ephemeral=True)
        chapters = get_chapters(book)
        if not chapters:
            await interaction.followup.send(
                f"No chapters found for book `{book}`. See `/bismillah books` for valid ids.",
                ephemeral=True,
            )
            return
        lines = [f"`{c['id']}` — {c['english']}" for c in chapters]
        lines.append(BOOKS_PAGE_HINT)
        await self._send_reference(
            interaction,
            f"**Chapters in book {book}** — use the number as `start_chapter_id` in `/bismillah setup`:",
            lines,
        )

    @app_commands.command(name="flags")
    @app_commands.describe(
        resolve="Hadith id to mark as dealt with (leave blank to just list open flags)"
    )
    async def flags(
        self, interaction: discord.Interaction, resolve: Optional[int] = None
    ):
        """Review hadiths readers have flagged. Bot owner only."""
        await interaction.response.defer(ephemeral=True)
        # Flags come in from every server the bot is in, so this is deliberately
        # not a per-guild admin command -- it would leak other servers' reports.
        if not await self.bot.is_owner(interaction.user):
            await interaction.followup.send(
                "Only the bot owner can review flags.", ephemeral=True
            )
            return

        if resolve is not None:
            closed = resolve_hadith_flags(resolve)
            await interaction.followup.send(
                f"Closed {closed} open flag(s) on hadith `{resolve}`."
                if closed
                else f"No open flags on hadith `{resolve}`.",
                ephemeral=True,
            )
            return

        open_flags = get_open_flags()
        if not open_flags:
            await interaction.followup.send("No open flags. 🎉", ephemeral=True)
            return

        # Group by hadith so a hadith several people flagged reads as one entry.
        grouped: dict[int, list[dict]] = {}
        for flag in open_flags:
            grouped.setdefault(flag["hadith_id"], []).append(flag)

        lines = []
        for hadith_id, entries in grouped.items():
            hadith = entries[0].get("hadiths") or {}
            snippet = " ".join((hadith.get("english_text") or "").split())[:160]
            lines.append(
                f"\n**`{hadith_id}`** — {len(entries)} flag(s) "
                f"· book {hadith.get('book_id')} ch {hadith.get('chapter_id')} "
                f"#{hadith.get('id_in_book')}\n{snippet}…"
            )
            for entry in entries:
                # <@id> renders as the member's name, so reports are attributable
                # without storing usernames that go stale when people rename.
                who = f"<@{entry['user_id']}>"
                where = entry.get("guild_name") or "unknown server"
                note = f" — “{entry['reason']}”" if entry.get("reason") else ""
                lines.append(f"↳ {who} in {where}{note}")
        lines.append(
            "\n-# `/bismillah flags resolve:<hadith id>` closes one; "
            "`/bismillah flag-reply` messages whoever reported it."
        )
        await self._send_reference(
            interaction, f"**{len(grouped)} flagged hadith(s)**", lines
        )

    @app_commands.command(name="flag-reply")
    @app_commands.describe(
        hadith="Hadith id to reply about (the id shown by /bismillah flags)",
        message="What to send the people who flagged it",
    )
    async def flag_reply(
        self, interaction: discord.Interaction, hadith: int, message: str
    ):
        """DM everyone who flagged a hadith. Bot owner only."""
        await interaction.response.defer(ephemeral=True)
        if not await self.bot.is_owner(interaction.user):
            await interaction.followup.send(
                "Only the bot owner can reply to reporters.", ephemeral=True
            )
            return

        flags = get_flags_for_hadith(hadith)
        if not flags:
            await interaction.followup.send(
                f"Nobody has flagged hadith `{hadith}`.", ephemeral=True
            )
            return

        body = compose_flag_reply(flags[0].get("hadiths") or {}, message)
        delivered, blocked = [], []
        # One DM per person even if they flagged from several servers.
        for user_id in dict.fromkeys(f["user_id"] for f in flags):
            try:
                user = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(
                    int(user_id)
                )
                await user.send(body)
                delivered.append(user_id)
            except (discord.Forbidden, discord.HTTPException, ValueError):
                # Closed DMs are the common case here, not an error worth raising.
                blocked.append(user_id)

        report = f"Sent to {len(delivered)} of {len(delivered) + len(blocked)} reporter(s)."
        if blocked:
            report += (
                "\nCouldn't DM "
                + ", ".join(f"<@{u}>" for u in blocked)
                + " — they likely have DMs from server members turned off."
            )
        await interaction.followup.send(report, ephemeral=True)


def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    bot = HadithBot()
    bot.tree.add_command(HadithCommands(bot))
    discord_token = os.getenv("DISCORD_TOKEN")

    if discord_token is None:
        raise Exception("DISCORD_TOKEN is not set")

    try:
        bot.run(discord_token or "", log_handler=None)
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()
