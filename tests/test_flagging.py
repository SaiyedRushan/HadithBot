"""Unit tests for the flag-a-hadith button.

These cover view assembly and custom_id round-tripping -- the parts that decide
whether a click on an old message still resolves after a restart. They import
views, not bot: bot pulls in db, which raises at import time without Supabase
credentials, so importing it here would make the suite fail to collect on CI.
"""

import re

import discord
import pytest

from utils import compose_flag_reply
from views import FlagHadithButton, build_hadith_view


def make_hadith(hadith_id=1234, text="This is the hadith text.") -> dict:
    return {
        "id": hadith_id,
        "id_in_book": 1,
        "english_narrator": "Narrated Abu Hurairah:",
        "english_text": text,
        "chapters": {"english": "Revelation"},
        "books_metadata": {"english_title": "Sahih al-Bukhari"},
    }


def buttons(view: discord.ui.View) -> list:
    """Every button in the view, unwrapping DynamicItems to the button inside."""
    out = []
    for item in view.children:
        if isinstance(item, discord.ui.Button):
            out.append(item)
        elif isinstance(item, discord.ui.DynamicItem):
            out.append(item.item)
    return out


# --- view assembly -----------------------------------------------------------

def test_view_has_lookup_and_flag_buttons():
    view = build_hadith_view(make_hadith())
    assert view is not None
    labels = [b.label for b in buttons(view)]
    assert "🔎 Look up on Sunnah.com" in labels
    assert "Flag an issue" in labels


def test_flag_button_carries_the_hadith_id():
    view = build_hadith_view(make_hadith(hadith_id=40991))
    ids = [b.custom_id for b in buttons(view) if b.custom_id]
    assert "flag_hadith:40991" in ids


def test_view_never_times_out():
    """A timeout would silently stop flag clicks working on older messages."""
    view = build_hadith_view(make_hadith())
    assert view is not None
    assert view.timeout is None


def test_flag_button_present_even_without_a_lookup_url():
    """A hadith with no usable search text still has to be flaggable."""
    hadith = make_hadith(text="")
    hadith["books_metadata"] = {"english_title": ""}
    view = build_hadith_view(hadith)
    assert view is not None
    ids = [b.custom_id for b in buttons(view) if b.custom_id]
    assert ids == ["flag_hadith:1234"]


def test_no_view_when_there_is_nothing_to_attach():
    hadith = make_hadith(text="")
    hadith["books_metadata"] = {"english_title": ""}
    del hadith["id"]
    assert build_hadith_view(hadith) is None


# --- custom_id round-trip ----------------------------------------------------

@pytest.mark.parametrize("hadith_id", [1, 40991, 50884])
def test_template_matches_ids_the_button_emits(hadith_id):
    """The click handler is found by matching this pattern against the custom_id,
    so an id the button can emit must be one the template can parse back."""
    custom_id = FlagHadithButton(hadith_id).custom_id
    match = re.fullmatch(FlagHadithButton.__discord_ui_compiled_template__.pattern, custom_id)
    assert match is not None
    assert int(match["hadith_id"]) == hadith_id


def test_custom_id_stays_within_discord_limit():
    """Discord rejects a custom_id over 100 characters."""
    assert len(FlagHadithButton(99999999).custom_id) <= 100


# --- reply composition -------------------------------------------------------

def test_reply_quotes_the_hadith_and_carries_the_message():
    body = compose_flag_reply(make_hadith(text="Actions are by intentions."), "Fixed now.")
    assert "Actions are by intentions." in body
    assert "Fixed now." in body
    assert body.startswith("Assalamu alaikum")


def test_reply_fits_in_one_discord_message():
    """A long hadith must not push the DM past Discord's cap and fail to send."""
    body = compose_flag_reply(make_hadith(text="word " * 3000), "Thanks for reporting.")
    assert len(body) <= 2000
    assert "Thanks for reporting." in body, "the reply itself must survive trimming"


def test_reply_survives_a_message_that_fills_the_limit():
    body = compose_flag_reply(make_hadith(text="word " * 3000), "x" * 1999)
    assert len(body) <= 2000


def test_reply_without_hadith_text_still_sends():
    body = compose_flag_reply({}, "We've corrected this.")
    assert "We've corrected this." in body
