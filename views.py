"""Discord message components for hadith messages: the lookup link and flag button.

Kept out of bot.py so the pieces worth testing can be imported without a database.
``db`` raises at import time when SUPABASE_URL is unset, and bot.py imports it at
module scope, so anything importing bot needs live credentials -- which CI does not
have. Nothing here needs a database except the moment a flag is actually saved, so
that import lives inside the handler (same reasoning as check_stale_channels).
"""

import logging
from typing import Optional

import discord

from utils import sunnah_url

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
                label="Flag an issue",
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


def build_hadith_view(hadith: dict) -> Optional[discord.ui.View]:
    """The buttons under a hadith: look it up, and flag it if it looks wrong.

    timeout=None keeps the view alive indefinitely; the flag button carries its
    hadith id in the custom_id so clicks still resolve after a restart (see
    FlagHadithButton). The link button never dispatches an interaction at all,
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
                label="🔎 Look up on Sunnah.com",
                style=discord.ButtonStyle.link,
                url=url,
            )
        )
    if hadith_id is not None:
        view.add_item(FlagHadithButton(int(hadith_id)))
    return view
