"""Discord message components: the hadith buttons (lookup, explain, flag), the verse of the day's links and the name match Play button.

Kept out of bot.py so the pieces worth testing can be imported without a database.
``db`` raises at import time when SUPABASE_URL is unset, and bot.py imports it at
module scope, so anything importing bot needs live credentials -- which CI does not
have. Nothing here needs a database except the moment a flag is actually saved, so
that import lives inside the handler (same reasoning as check_stale_channels).
"""

import logging
from typing import Optional

import discord

from quran import Ayah, chatgpt_url, quran_com_url, tafsir_url
from utils import (
    FLAG_ALERT_USER_ID,
    compose_explain_reply,
    compose_flag_alert,
    sunnah_url,
)

logger = logging.getLogger("HadithBot")


class FlagReasonModal(discord.ui.Modal, title="Flag this hadith"):
    """Asks what looks wrong before recording the report.

    A bare click tells us a hadith is suspect but not why, and the failure modes
    differ a lot (text cut off, wrong attribution, a mismatch with sunnah.com).
    The note is optional so a reader who just wants to raise a hand still can.
    """

    reason = discord.ui.TextInput(
        label="What looks wrong?",
        style=discord.TextStyle.paragraph,
        placeholder=(
            "e.g. the text stops mid-sentence, or it doesn't match what's on sunnah.com"
        ),
        required=False,
        max_length=500,
    )

    def __init__(self, hadith_id: int):
        super().__init__()
        self.hadith_id = hadith_id

    async def on_submit(self, interaction: discord.Interaction):
        from db import save_hadith_flag  # imported here: see module docstring

        guild = interaction.guild
        try:
            save_hadith_flag(
                hadith_id=self.hadith_id,
                user_id=str(interaction.user.id),
                reason=(self.reason.value or "").strip() or None,
                guild_id=str(guild.id) if guild else None,
                guild_name=guild.name if guild else None,
                channel_id=str(interaction.channel_id) if interaction.channel_id else None,
            )
        except Exception:
            logger.error(
                f"Failed to save flag for hadith {self.hadith_id}", exc_info=True
            )
            await interaction.response.send_message(
                "Couldn't record that just now — please try again in a moment.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "JazakAllahu khayran — this hadith has been flagged for review. 🚩",
            ephemeral=True,
        )
        # After the reader's reply, and in its own try: the flag is already
        # saved, so a DM that fails must not look like a failed report.
        try:
            await self.alert_maintainer(interaction)
        except Exception:
            logger.error(
                f"Saved the flag on hadith {self.hadith_id} but couldn't DM "
                f"user {FLAG_ALERT_USER_ID} about it",
                exc_info=True,
            )

    async def alert_maintainer(self, interaction: discord.Interaction):
        from db import count_hadith_flags, get_hadith_by_id  # see module docstring

        message = interaction.message
        guild = interaction.guild
        body = compose_flag_alert(
            get_hadith_by_id(self.hadith_id),
            self.hadith_id,
            str(interaction.user.id),
            (self.reason.value or "").strip() or None,
            guild.name if guild else None,
            count_hadith_flags(self.hadith_id),
            jump_url=message.jump_url if message else None,
        )
        client = interaction.client
        user = client.get_user(FLAG_ALERT_USER_ID) or await client.fetch_user(
            FLAG_ALERT_USER_ID
        )
        await user.send(body)


class FlagHadithButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"flag_hadith:(?P<hadith_id>\d+)",
):
    """The 🚩 button under every hadith message.

    A DynamicItem rather than a plain callback button because the hadith id has
    to live in the custom_id: messages outlive the process, and the bot must be
    able to handle a click on a hadith it posted weeks ago without holding any
    per-message state in memory.
    """

    def __init__(self, hadith_id: int):
        self.hadith_id = hadith_id
        super().__init__(
            discord.ui.Button(
                label="Report",
                emoji="🚩",
                style=discord.ButtonStyle.secondary,
                custom_id=f"flag_hadith:{hadith_id}",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item, match, /):
        return cls(int(match["hadith_id"]))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FlagReasonModal(self.hadith_id))


class ExplainHadithButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"explain_hadith:(?P<hadith_id>\d+)",
):
    """The 💬 Ask ChatGPT button: replies privately with a ChatGPT link that has the whole hadith typed in.

    Not a link button: Discord caps a button's URL at 512 chars, which fits only
    ~400 chars of hadith. A link inside an embed can be ~4000. The hadith is
    re-read from the database by id so clicks on old messages still work.
    """

    def __init__(self, hadith_id: int):
        self.hadith_id = hadith_id
        super().__init__(
            discord.ui.Button(
                label="Ask ChatGPT",
                emoji="💬",
                style=discord.ButtonStyle.secondary,
                custom_id=f"explain_hadith:{hadith_id}",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item, match, /):
        return cls(int(match["hadith_id"]))

    async def callback(self, interaction: discord.Interaction):
        from db import get_hadith_by_id  # imported here: see module docstring

        try:
            hadith = get_hadith_by_id(self.hadith_id)
        except Exception:
            logger.error(
                f"Failed to load hadith {self.hadith_id} to explain", exc_info=True
            )
            hadith = None
        if not hadith:
            await interaction.response.send_message(
                "Couldn't load this hadith just now. Please try again in a minute.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=discord.Embed(description=compose_explain_reply(hadith)),
            ephemeral=True,
        )


def build_hadith_view(hadith: dict) -> Optional[discord.ui.View]:
    """The buttons under a hadith: look it up, ask ChatGPT about it, flag it.

    timeout=None keeps the view alive indefinitely; the explain and flag buttons
    carry the hadith id in their custom_id so clicks still resolve after a
    restart (see FlagHadithButton). The link button never dispatches an interaction at all,
    so it needs no handling either way.

    Returns None only when there is nothing to attach -- a hadith with no usable
    id and no search URL.
    """
    url = sunnah_url(hadith)
    hadith_id = hadith.get("id")
    if not url and hadith_id is None:
        return None
    view = discord.ui.View(timeout=None)
    if url:
        view.add_item(
            discord.ui.Button(
                label="Sunnah.com",
                emoji="🔎",
                style=discord.ButtonStyle.link,
                url=url,
            )
        )
    if hadith_id is not None:
        view.add_item(ExplainHadithButton(int(hadith_id)))
        view.add_item(FlagHadithButton(int(hadith_id)))
    return view


def build_ayah_view(ayah: Ayah) -> discord.ui.View:
    """The buttons under the verse of the day: its tafsir, the verse on Quran.com, ChatGPT.

    All links, so a click never reaches the bot and old messages need no handling.
    """
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label="Read tafsir",
            emoji="📖",
            style=discord.ButtonStyle.link,
            url=tafsir_url(ayah),
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Listen",
            emoji="🔊",
            style=discord.ButtonStyle.link,
            url=quran_com_url(ayah),
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Ask ChatGPT",
            emoji="💬",
            style=discord.ButtonStyle.link,
            url=chatgpt_url(ayah),
        )
    )
    return view


class PlayNameMatchButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"play_name_match",
):
    """The Play button on the daily name match card: opens the game in Discord.

    The game finds today's match from the channel it was opened in, so the
    button carries nothing but its name, and every day's card can share it.
    """

    def __init__(self):
        super().__init__(
            discord.ui.Button(
                label="Play today's match",
                style=discord.ButtonStyle.primary,
                custom_id="play_name_match",
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item, match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.launch_activity()
        except discord.HTTPException as e:
            logger.warning(f"Couldn't launch the name match: {e}")
            if interaction.response.is_done():
                return
            await interaction.response.send_message(
                "Couldn't open the game. To play, you need the \"Use Activities\" "
                "permission in this channel, which a server admin can turn on in the "
                "channel's settings.",
                ephemeral=True,
            )


def build_name_match_view(final: bool = False) -> discord.ui.View:
    """The buttons under the name match card.

    A finished day keeps only the MugUp link, so nobody opens a closed match
    from an old card.
    """
    from name_match import MUGUP_NAMES_URL

    view = discord.ui.View(timeout=None)
    if not final:
        view.add_item(PlayNameMatchButton())
    view.add_item(
        discord.ui.Button(
            label="All 99 names on MugUp",
            style=discord.ButtonStyle.link,
            url=MUGUP_NAMES_URL,
        )
    )
    return view
