"""Unit tests for the pure formatting/util logic in utils.py.

These cover the message-formatting helpers, which have no Discord or database
dependencies, so they run anywhere with no configuration.
"""

from utils import (
    Name,
    find_last_newline,
    getNameFormattedMessage,
    getHadithFormattedMessage,
)

DISCORD_MAX = 2000


def make_name() -> Name:
    return Name(
        number=1,
        name="الرحمن",
        transliteration="Ar-Rahman",
        found="Quran 1:1",
        en={"meaning": "The Most Compassionate", "desc": "the most merciful"},
        fr={"meaning": "Le Tout Misericordieux", "desc": "le plus clement"},
    )


def make_hadith(text: str = "This is the hadith text.", id_in_book: int = 1) -> dict:
    return {
        "id_in_book": id_in_book,
        "english_narrator": "Narrated Abu Hurairah:",
        "english_text": text,
        "chapters": {"english": "Revelation"},
        "books_metadata": {"english_title": "Sahih al-Bukhari"},
    }


# --- find_last_newline -------------------------------------------------------

def test_find_last_newline_prefers_paragraph_break():
    msg = "first para\n\nsecond para"
    idx = find_last_newline(msg)
    assert idx == 12
    assert msg[:idx].endswith("\n\n")


def test_find_last_newline_falls_back_to_period():
    msg = "sentence one. sentence two"
    idx = find_last_newline(msg)
    # No paragraph break, so it splits just past the last period.
    assert idx == msg.rfind(".") + 2


# --- getNameFormattedMessage -------------------------------------------------

def test_get_name_formatted_message_includes_all_fields():
    out = getNameFormattedMessage(make_name())
    assert out.startswith("> ")
    assert "(1)" in out
    assert "Ar-Rahman" in out
    assert "The Most Compassionate" in out
    assert "the most merciful" in out


# --- getHadithFormattedMessage ----------------------------------------------

def test_get_hadith_formatted_message_has_header_and_body():
    msgs = getHadithFormattedMessage(make_hadith())
    assert isinstance(msgs, list) and len(msgs) >= 2
    # First message is the book/chapter header.
    assert "Sahih al-Bukhari" in msgs[0]
    assert "Revelation" in msgs[0]
    # Body carries narrator + text.
    body = " ".join(msgs[1:])
    assert "Abu Hurairah" in body
    assert "hadith text" in body


def test_get_hadith_formatted_message_respects_discord_limit():
    long_text = "word. " * 1000  # ~6000 chars, well over the 2000 limit
    msgs = getHadithFormattedMessage(make_hadith(text=long_text))
    assert len(msgs) > 1, "long hadith should be split into multiple messages"
    assert all(len(m) <= DISCORD_MAX for m in msgs), "every chunk must fit Discord's 2000-char limit"
