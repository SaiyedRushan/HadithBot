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
    get_random_hadith,
    remove_channel_state,
    save_channel_state,
)
from utils import Name, getHadithFormattedMessage, getNameFormattedMessage, sunnah_url


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

    # @tasks.loop(seconds=10)
    @tasks.loop(time=time(hour=18, tzinfo=ZoneInfo("America/Toronto")))
    async def send_daily_message(self):
        """Loops through the active channels and sends daily messages"""
        try:
            channels = get_channels()
        except Exception as e:
            self.logger.error(f"Failed to fetch active channels: {e}")
            return

        for channel_row in channels.data:
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

                # get hadith for the given hadith number, book number, chapter number and send message
                hadith = get_hadith_in_same_chapter_and_book(
                    last_hadith_no, last_book_no, last_chapter_no, hadiths_per_day
                )

                if hadith:
                    for h in hadith:
                        await self.send_formatted_hadith(channel, h)
                        last_hadith_no = h["id_in_book"]

                    # Calculate next hadith position for tomorrow
                    next_hadith_no = last_hadith_no + 1

                    save_channel_state(
                        channel_id,
                        next_hadith_no,
                        current_name_index,
                        last_book_no,
                        last_chapter_no,
                    )

                    self.logger.info(
                        f"Successfully sent hadith from book {last_book_no}, chapter {last_chapter_no}, hadith {last_hadith_no}"
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

    @staticmethod
    def _hadith_link_view(hadith: dict) -> Optional[discord.ui.View]:
        """A 'Look up on Sunnah.com' link button for the hadith, or None if no URL.

        Link-style buttons never dispatch interactions, so the view needs no
        callback handling or registration -- it keeps working indefinitely.
        """
        url = sunnah_url(hadith)
        if not url:
            return None
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="🔎 Look up on Sunnah.com",
                style=discord.ButtonStyle.link,
                url=url,
            )
        )
        return view

    async def send_formatted_hadith(self, channel: discord.TextChannel, hadith: dict):
        """Send formatted hadith message"""
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        # Attach the link button to the last chunk so it sits under the full hadith.
        view = self._hadith_link_view(hadith)
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
        view = self._hadith_link_view(hadith)
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
        start_hadith_id="Hadith id to start from (blank keeps current)",
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

        save_channel_state(
            str(target.id),
            pick(start_hadith_id, "last_hadith_no", 1),
            pick(start_name, "last_name_no", 1),
            pick(start_book_id, "last_book_id", 1),
            pick(start_chapter_id, "last_chapter_id", 1),
            active=True,
            hadiths_per_day=hpd,
            names_per_day=npd,
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
        await self._send_reference(
            interaction,
            f"**Chapters in book {book}** — use the number as `start_chapter_id` in `/bismillah setup`:",
            lines,
        )


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
