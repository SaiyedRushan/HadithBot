"""The divider line between the items of a daily message.

The send methods are called as unbound functions against a stub, the same way
tests/test_delivery_alerts.py does it, so no discord.py client is needed.
"""

import asyncio
from types import SimpleNamespace

from bot import HadithBot
from utils import DIVIDER, Name, getHadithFormattedMessage, with_divider


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content, view=None):
        self.sent.append(SimpleNamespace(content=content, view=view))


def make_name(number: int) -> Name:
    return Name(
        number=number,
        name="الرحمن",
        transliteration="Ar-Rahman",
        found="Quran 1:1",
        en={"meaning": "The Most Compassionate", "desc": "the most merciful"},
        fr={"meaning": "Le Tout Misericordieux", "desc": "le plus clement"},
    )


def make_hadith(text: str = "This is the hadith text.") -> dict:
    return {
        "hadith_id": 1,
        "id_in_book": 1,
        "english_narrator": "Narrated Abu Hurairah:",
        "english_text": text,
        "chapters": {"english": "Revelation"},
        "books_metadata": {"english_title": "Sahih al-Bukhari"},
    }


def has_divider(message) -> bool:
    return message.content.startswith(DIVIDER + "\n")


def test_divider_keeps_a_heading_on_its_own_line():
    # Discord only renders ### as a heading at the start of a line.
    assert with_divider("### Heading").split("\n") == [DIVIDER, "### Heading"]


def test_divider_goes_between_names_but_not_above_the_first():
    channel = FakeChannel()
    names = [make_name(1), make_name(2), make_name(3)]
    asyncio.run(HadithBot.send_formatted_name(None, channel, names))
    assert [has_divider(m) for m in channel.sent] == [False, True, True]


def test_first_name_gets_a_divider_after_the_verse():
    channel = FakeChannel()
    names = [make_name(1), make_name(2)]
    asyncio.run(HadithBot.send_formatted_name(None, channel, names, after_verse=True))
    assert [has_divider(m) for m in channel.sent] == [True, True]


def test_hadith_divider_is_above_the_heading_only():
    channel = FakeChannel()
    hadith = make_hadith("word. " * 1000)  # long enough to split across messages
    asyncio.run(HadithBot.send_formatted_hadith(None, channel, hadith, divider=True))
    assert len(channel.sent) > 2
    assert [has_divider(m) for m in channel.sent] == [True] + [False] * (len(channel.sent) - 1)
    assert channel.sent[0].content.split("\n")[1].startswith("### 📖")


def test_hadith_has_no_divider_unless_asked():
    channel = FakeChannel()
    asyncio.run(HadithBot.send_formatted_hadith(None, channel, make_hadith()))
    assert not any(has_divider(m) for m in channel.sent)


def test_divider_does_not_push_a_hadith_message_over_the_limit():
    hadith = make_hadith("word. " * 1000)
    first, *rest = getHadithFormattedMessage(hadith)
    assert len(with_divider(first)) <= 2000
    assert all(len(m) <= 2000 for m in rest)


def test_banners_carry_the_divider():
    channel = FakeChannel()
    asyncio.run(HadithBot.send_new_book_message(None, channel, make_hadith()))
    asyncio.run(HadithBot.send_new_chapter_message(None, channel, make_hadith()))
    assert all(has_divider(m) for m in channel.sent)
