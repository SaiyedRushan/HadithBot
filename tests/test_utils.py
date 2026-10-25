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
    channel_max,
    daily_count,
    load_custom_limits,
    setup_reply,
    stopped_text,
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
    # A heading, not a blockquote -- quoted text is indented and wraps more.
    assert out.startswith("### ")
    assert "> " not in out
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
    # No blockquote anywhere: the indent it adds costs width on every line.
    assert not any(m.lstrip().startswith("> ") for m in msgs)


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


# --- daily counts ------------------------------------------------------------

def test_daily_count_defaults_to_one():
    assert daily_count(None) == 1


def test_daily_count_caps_old_settings_at_three():
    """Channels saved when up to 10 was allowed now get 3."""
    assert daily_count(10) == 3
    assert daily_count(4) == 3


def test_daily_count_keeps_values_in_range():
    assert [daily_count(n) for n in (1, 2, 3)] == [1, 2, 3]
    assert daily_count(0) == 1


def test_setup_reply_recommends_one_when_more_is_chosen():
    reply = setup_reply("#daily", "set up for", 3, 1)
    assert "3 hadiths and 1 name a day" in reply
    assert "We recommend 1 hadith and 1 name a day" in reply


def test_setup_reply_skips_the_nudge_at_one_and_one():
    reply = setup_reply("#daily", "set up for", 1, 1)
    assert reply == "Daily messages set up for #daily: 1 hadith and 1 name a day."


def test_custom_limits_raise_one_channel_and_ignore_notes(tmp_path):
    path = tmp_path / "custom_limits.json"
    path.write_text(
        '{"_note": "ignored", "111": {"max_per_day": 5}, "222": {"max_per_day": 50}}'
    )
    limits = load_custom_limits(path)
    assert limits == {"111": 5, "222": 10}  # 50 held to the 10 ceiling
    assert channel_max(111, limits) == 5
    assert channel_max("333", limits) == 3
    assert daily_count(10, channel_max("111", limits)) == 5


def test_custom_limits_missing_file_means_no_exceptions(tmp_path):
    assert load_custom_limits(tmp_path / "nope.json") == {}


def test_shipped_custom_limits_file_is_valid():
    """load_custom_limits swallows a broken file at runtime; catch it here instead."""
    import json

    from utils import CUSTOM_LIMITS_FILE

    for key, entry in json.loads(CUSTOM_LIMITS_FILE.read_text()).items():
        if not key.startswith("_"):
            assert key.isdigit() and int(entry["max_per_day"]) >= 1


def test_stopped_text_says_when_and_why():
    row = {"stopped_at": "2026-10-25T23:30:00+00:00", "stopped_reason": "stopped_by_admin"}
    # 23:30 UTC is still Oct 25 in Toronto.
    assert stopped_text(row).startswith("Stopped on Oct 25: someone ran `/bismillah stop`.")
    assert stopped_text(row | {"stopped_reason": "channel_deleted"}) == (
        "Stopped on Oct 25: the channel was deleted."
    )


def test_stopped_text_without_a_date_or_known_reason():
    assert stopped_text({"stopped_reason": "bot_removed"}) == (
        "Stopped: HadithBot was removed from this server."
    )
    assert stopped_text({"stopped_at": "2026-10-25T12:00:00Z", "stopped_reason": "?"}) == (
        "Stopped on Oct 25: no reason was recorded."
    )
