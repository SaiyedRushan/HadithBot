"""Unit tests for the pure formatting/util logic in utils.py.

These cover the message-formatting helpers, which have no Discord or database
dependencies, so they run anywhere with no configuration.
"""

from utils import (
    Name,
    find_last_newline,
    getNameFormattedMessage,
    getHadithFormattedMessage,
    sunnah_url,
    resolve_start_position,
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


def test_get_name_formatted_message_includes_dua_note_when_present():
    name = make_name()
    name.en["dua"] = "Call upon Ar-Rahman when seeking mercy."
    out = getNameFormattedMessage(name)
    assert "In your dua:" in out
    assert "Call upon Ar-Rahman when seeking mercy." in out


def test_get_name_formatted_message_omits_dua_note_when_absent():
    # The dua note is optional; names without it must still render cleanly.
    out = getNameFormattedMessage(make_name())
    assert "In your dua:" not in out


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


def test_get_hadith_formatted_message_omits_internal_number():
    # id_in_book doesn't match sunnah.com's reference numbers, so it must not be
    # shown as a "#N" citation -- the Sunnah.com button is the canonical pointer.
    msgs = getHadithFormattedMessage(make_hadith(id_in_book=1000))
    body = " ".join(msgs)
    assert "#1000" not in body
    assert "1000" not in body


def test_get_hadith_formatted_message_respects_discord_limit():
    long_text = "word. " * 1000  # ~6000 chars, well over the 2000 limit
    msgs = getHadithFormattedMessage(make_hadith(text=long_text))
    assert len(msgs) > 1, "long hadith should be split into multiple messages"
    assert all(len(m) <= DISCORD_MAX for m in msgs), "every chunk must fit Discord's 2000-char limit"


# --- sunnah_url --------------------------------------------------------------

def test_sunnah_url_is_text_search_not_deep_link():
    # id_in_book does NOT map to sunnah.com reference numbers, so a deep link by
    # number would point at the wrong hadith -- we link to a text search instead.
    h = make_hadith(text="The Prophet went out towards the Musalla for the Istisqa prayer.")
    url = sunnah_url(h)
    assert url.startswith("https://sunnah.com/search?q=")
    assert "Musalla" in url  # a distinctive word from the text seeds the query
    assert "bukhari:" not in url  # never a (mis-aligned) deep link by number


def test_sunnah_url_uses_leading_words_up_to_the_word_cap():
    long_text = " ".join(f"word{i}" for i in range(50))
    url = sunnah_url(make_hadith(text=long_text))
    assert "word0" in url and "word24" in url  # leading words up to the 25-word cap
    assert "word25" not in url  # later words are dropped to keep the query tight


def test_sunnah_url_stays_under_discord_button_url_limit():
    # The longest real hadith is ~9.7k chars; the URL must still be sendable as a
    # Discord link button, which caps url at 512 characters.
    huge = "Heraclius " * 3000
    url = sunnah_url(make_hadith(text=huge))
    assert len(url) <= 512


def test_sunnah_url_strips_the_honorific_glyph():
    url = sunnah_url(make_hadith(text="The Messenger of Allah (ﷺ) said something."))
    assert "%EF" not in url and "ﷺ" not in url  # the ﷺ glyph isn't in the query


def test_sunnah_url_falls_back_to_title_without_text():
    url = sunnah_url(make_hadith(text=""))
    assert url.startswith("https://sunnah.com/search?q=")
    assert "Bukhari" in url  # falls back to the book title


def test_sunnah_url_returns_none_without_text_or_title():
    assert sunnah_url({"english_text": "", "books_metadata": {}}) is None


# --- resolve_start_position --------------------------------------------------

EXISTING = {"last_book_id": 3, "last_chapter_id": 40, "last_hadith_no": 1200}


def test_resolve_start_position_changing_chapter_resets_to_first_hadith():
    # Set a new chapter, leave hadith blank -> start at the chapter's first
    # hadith (1), not the stale 1200 that would overshoot the chapter.
    book, chapter, hadith = resolve_start_position(EXISTING, None, 5, None)
    assert (book, chapter, hadith) == (3, 5, 1)


def test_resolve_start_position_changing_book_resets_chapter_and_hadith():
    # Changing the book without a chapter must not keep book 3's chapter 40;
    # it resets to the new book's start (chapter 1, hadith 1, resolved at fetch).
    assert resolve_start_position(EXISTING, 7, None, None) == (7, 1, 1)


def test_resolve_start_position_explicit_hadith_wins():
    book, chapter, hadith = resolve_start_position(EXISTING, 7, 2, 99)
    assert (book, chapter, hadith) == (7, 2, 99)


def test_resolve_start_position_no_positional_change_keeps_current():
    # Only counts/name changed elsewhere -> position untouched, including hadith.
    assert resolve_start_position(EXISTING, None, None, None) == (3, 40, 1200)


def test_resolve_start_position_new_channel_defaults_to_one():
    assert resolve_start_position(None, None, None, None) == (1, 1, 1)


def test_resolve_start_position_new_channel_with_chapter_starts_at_first_hadith():
    assert resolve_start_position(None, None, 12, None) == (1, 12, 1)
