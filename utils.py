from typing import Dict, Optional
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import logging
import os
from urllib.parse import quote, urlencode
import re

_SUNNAH_SEARCH = "https://sunnah.com/search?q="
# Use the opening words of the hadith as the search phrase. More words sharpen
# the match (some hadiths share a generic opening with a parallel narration),
# but Discord caps a link-button URL at 512 chars, so we also stop once the
# encoded URL nears that ceiling -- the longest hadith here is ~9.7k chars and
# would otherwise produce a ~12k-char URL Discord rejects outright.
_MAX_WORDS = 25
_MAX_URL_LEN = 500  # safely under Discord's 512-char button-URL limit


def sunnah_url(hadith) -> Optional[str]:
    """Build a sunnah.com link so readers can look a hadith up for more info.

    This dataset's ``id_in_book`` is a sequential 1, 2, 3... counter per book.
    It does NOT line up with sunnah.com's published reference numbers, which use
    compound entries (e.g. 3000a / 3000b) and differ in total count per book. A
    deep link like ``sunnah.com/bukhari:<id_in_book>`` therefore matches only at
    hadith #1 and then drifts -- landing on the wrong hadith, or 404ing, for the
    rest of the book (verified against sunnah.com across several collections).

    So instead we link to a sunnah.com text search seeded with the opening words
    of the hadith's English text. That distinctive snippet brings the exact
    hadith back as the top result (or, for hadiths with a near-identical
    parallel narration, that sibling -- still the same content), and the link is
    correct for every book.
    """
    text = (hadith.get("english_text") or "").replace("ﷺ", " ")  # drop the ﷺ glyph
    # ASCII words/digits only: enough to match (names like "Muzdalifa"/"Uhban"
    # come through) without dragging in diacritics that could break a match.
    words = re.findall(r"[A-Za-z0-9']+", text)[:_MAX_WORDS]
    # Add words while the encoded URL stays under Discord's button-URL limit, so
    # a long hadith never yields a URL Discord refuses to send.
    chosen: list[str] = []
    for word in words:
        candidate = " ".join(chosen + [word])
        if len(_SUNNAH_SEARCH + quote(candidate)) > _MAX_URL_LEN:
            break
        chosen.append(word)
    query = " ".join(chosen)
    if not query:
        # No usable text (rare) -- fall back to the book title so the link still
        # points somewhere relevant rather than nowhere.
        title = (hadith.get("books_metadata") or {}).get("english_title") or ""
        query = title[:100]  # titles are short, but stay within the URL budget
    if not query:
        return None
    return f"{_SUNNAH_SEARCH}{quote(query)}"


_CHATGPT = "https://chatgpt.com/?"
# The explain link goes in an embed description (4096 chars), not on a link
# button: a button URL caps at 512, which fits barely 400 chars of hadith.
# This leaves room for the sentences around the link.
_EXPLAIN_URL_BUDGET = 3700


def chatgpt_explain_url(hadith: dict) -> tuple[str, bool]:
    """A chatgpt.com link with a request to explain this hadith already typed in.

    Returns the URL and whether the hadith text had to be cut short to fit. The
    book and chapter go in the prompt because ChatGPT can't look the hadith up by
    number (``id_in_book`` doesn't match published numbering, see sunnah_url).
    """
    book = (hadith.get("books_metadata") or {}).get("english_title") or ""
    chapter = (hadith.get("chapters") or {}).get("english") or ""
    source = f" from {book}" if book else ""
    if chapter:
        source += f', chapter "{chapter}"'
    head = (
        f"Please explain this hadith{source}. What does it mean, and what "
        "lessons do scholars take from it?\n\n"
    )
    body = " ".join(
        f"{hadith.get('english_narrator') or ''} {hadith.get('english_text') or ''}".split()
    )

    def build(text: str) -> str:
        return _CHATGPT + urlencode({"q": head + text})

    url = build(body)
    if len(url) <= _EXPLAIN_URL_BUDGET:
        return url, False
    # Too long: drop whole words from the end until it fits.
    words = body.split(" ")
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(build(" ".join(words[:mid]) + " …")) <= _EXPLAIN_URL_BUDGET:
            lo = mid
        else:
            hi = mid - 1
    return build(" ".join(words[:lo]) + " …"), True


def compose_explain_reply(hadith: dict) -> str:
    """The private reply to "Ask ChatGPT to explain": a link plus what to expect."""
    url, cut = chatgpt_explain_url(hadith)
    lines = [f"**[Open ChatGPT with this hadith]({url})**"]
    lines.append("It opens in your browser with the question already typed in.")
    if cut:
        lines.append(
            "This hadith is too long to fit in one link, so ChatGPT gets the "
            "first part of it."
        )
    lines.append(
        "ChatGPT is not a scholar and can get things wrong. Check anything "
        "important with someone knowledgeable."
    )
    return "\n".join(lines)


# Daily counts per channel. Capped at 3 because servers that picked a large
# number tended to get overwhelmed and remove the bot; 1 is the default and
# what the setup reply recommends.
DEFAULT_PER_DAY = 1
MAX_PER_DAY = 3
# Ceiling for channels given a higher limit on request (see custom_limits.json).
ABSOLUTE_MAX_PER_DAY = 10
CUSTOM_LIMITS_FILE = Path(__file__).resolve().parent / "data" / "custom_limits.json"


def load_custom_limits(path: Path = CUSTOM_LIMITS_FILE) -> dict[str, int]:
    """Channels allowed more than MAX_PER_DAY, as {channel_id: their max}.

    Servers ask for this by email (the update message and the setup error point
    them to support@hadithbot.app). Add an entry like
    ``"123456789": {"max_per_day": 5, "note": "Server name, emailed 2026-10-22"}``;
    keys starting with "_" are notes and ignored. Read fresh each broadcast, so
    a change applies from the next daily send.
    """
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        logging.getLogger("HadithBot").error(
            f"Couldn't read {path.name}; every channel gets the default cap",
            exc_info=True,
        )
        return {}
    return {
        str(channel_id): max(1, min(int(entry["max_per_day"]), ABSOLUTE_MAX_PER_DAY))
        for channel_id, entry in raw.items()
        if not str(channel_id).startswith("_")
    }


def channel_max(channel_id, limits: Optional[dict[str, int]] = None) -> int:
    """Most hadiths (or names) a day this channel may get."""
    if limits is None:
        limits = load_custom_limits()
    return limits.get(str(channel_id), MAX_PER_DAY)


def daily_count(value: Optional[int], cap: int = MAX_PER_DAY) -> int:
    """A stored hadiths/names-per-day value, held to 1..cap.

    Channels set up before the cap may still have up to 10 saved; this is what
    keeps them at 3 without rewriting their rows.
    """
    if value is None:
        return DEFAULT_PER_DAY
    return max(1, min(int(value), cap))


def setup_reply(target_mention: str, verb: str, hadiths: int, names: int) -> str:
    """What /bismillah setup says once it has saved, with a nudge toward 1 and 1."""
    hadith_word = "hadith" if hadiths == 1 else "hadiths"
    name_word = "name" if names == 1 else "names"
    reply = (
        f"Daily messages {verb} {target_mention}: "
        f"{hadiths} {hadith_word} and {names} {name_word} a day."
    )
    if hadiths > 1 or names > 1:
        reply += (
            "\n\nWe recommend 1 hadith and 1 name a day. A lot of messages "
            "every day can start to feel like too much, and a short reading is "
            "easier to keep up with. You can change it any time with "
            "`/bismillah setup`."
        )
    return reply


UPDATES_DIR = Path(__file__).resolve().parent / "updates"


def update_for(day: date, directory: Path = UPDATES_DIR) -> Optional[str]:
    """The update message dated ``day`` (updates/YYYY-MM-DD.md), if there is one.

    The daily broadcast posts it in every channel just before that day's
    hadith, so each update goes out exactly once, on its date, with no record
    of who has seen it. Anything over Discord's 2000-char limit is skipped
    rather than cut (tests/test_send_update.py keeps that from shipping).
    """
    path = directory / f"{day.isoformat()}.md"
    try:
        text = path.read_text().strip()
    except FileNotFoundError:
        return None
    return text if 0 < len(text) <= 2000 else None


_DM_LIMIT = 2000  # Discord's per-message character cap


def compose_flag_reply(hadith: dict, message: str) -> str:
    """The DM a reporter gets back about a hadith they flagged.

    Quotes enough of the hadith for them to recognise which report this answers
    -- a bare reply weeks later is meaningless -- then the operator's message.
    Trimmed to fit one Discord message, shortening the quote rather than the
    reply, since the reply is the part that carries the information.
    """
    text = " ".join((hadith.get("english_text") or "").split())
    message = message.strip()
    head = "Assalamu alaikum — about the hadith you flagged:\n"
    tail = f"\n\n{message}" if message else ""
    budget = _DM_LIMIT - len(head) - len(tail) - len("> …\n")
    if budget < 0:
        # Reply alone fills the message; send it without the quote.
        return (head + tail).strip()[:_DM_LIMIT]
    quote = text[:budget]
    if len(text) > len(quote):
        quote = quote.rstrip() + "…"
    return f"{head}> {quote}{tail}" if quote else (head + tail).strip()


# saiyedrushan. Not the application's owner: the bot belongs to a developer
# team whose owner is a different account, so "DM the owner" would go to the
# wrong person. FLAG_ALERT_USER_ID overrides it for a test bot.
FLAG_ALERT_USER_ID = int(os.environ.get("FLAG_ALERT_USER_ID") or 364012496358735883)

_FLAG_SNIPPET = 300  # enough of the hadith to recognise it without opening it


def compose_flag_alert(
    hadith: Optional[dict],
    hadith_id: int,
    reporter_id: str,
    reason: Optional[str],
    guild_name: Optional[str],
    open_count: int,
    jump_url: Optional[str] = None,
) -> str:
    """The DM the maintainer gets the moment a reader reports a hadith.

    Says which hadith, who reported it, where, and why, so most reports can be
    judged from the DM alone, then names the commands that act on it.
    """
    hadith = hadith or {}
    book = (hadith.get("books_metadata") or {}).get("english_title")
    chapter = (hadith.get("chapters") or {}).get("english")
    number = hadith.get("id_in_book")
    place = ", ".join(
        p for p in (book, chapter, f"hadith {number}" if number else None) if p
    )

    lines = [f"🚩 **A hadith was reported** in **{guild_name or 'a DM'}**"]
    lines.append(f"Reported by <@{reporter_id}>")
    others = open_count - 1
    if others > 0:
        lines.append(
            f"{others} other {'person has' if others == 1 else 'people have'} "
            "reported this hadith too."
        )
    lines.append(f"\n**Hadith `{hadith_id}`**" + (f": {place}" if place else ""))
    text = " ".join((hadith.get("english_text") or "").split())
    if text:
        snippet = text[:_FLAG_SNIPPET]
        if len(text) > len(snippet):
            snippet = snippet.rstrip() + "…"
        lines.append(f"> {snippet}")
    lines.append(f"\n**Their note:** {reason}" if reason else "\nThey didn't leave a note.")
    if jump_url:
        lines.append(f"[Open the message they reported]({jump_url})")
    lines.append(
        f"\n-# Close it with `/bismillah flags resolve:{hadith_id}`. "
        f"Reply to them with `/bismillah flag-reply hadith:{hadith_id}`."
    )
    return "\n".join(lines)[:_DM_LIMIT]


@dataclass
class Name:
    number: int
    name: str
    transliteration: str
    found: str
    en: Dict[str, str]
    fr: Dict[str, str]


def getHadithFormattedMessage(hadith) -> list[str]:
    # A heading, not a blockquote: Discord indents quoted text behind a vertical
    # bar, which on a phone eats a chunk of every line's width and wraps the
    # hadith far more than it needs to. A heading marks the start of each hadith
    # just as clearly and leaves the body at full width.
    formatted_messages = []
    formatted_messages.append(f"### 📖 Book: {hadith['books_metadata']['english_title']} - Chapter: {hadith['chapters']['english']}\n")
    # We deliberately don't show id_in_book here: it's a sequential per-book
    # counter that does NOT match sunnah.com's published reference numbers, so a
    # "#1000" would read as a citation a reader couldn't reproduce. The
    # Sunnah.com link button is the canonical pointer instead.
    formatted_hadith = f"{hadith['english_narrator']} {hadith['english_text']}\n\n"
    formatted_hadith = re.sub(r'\s+', ' ', formatted_hadith).strip()

    # while formatted_hadith is not empty
    while formatted_hadith:
        if len(formatted_hadith) <= 2000:
            formatted_messages.append(formatted_hadith)
            formatted_hadith = ""
        else:
            split_index = find_last_newline(formatted_hadith[:2000])
            if split_index == -1:
                split_index = 2000
            formatted_messages.append(formatted_hadith[:split_index])
            formatted_hadith = formatted_hadith[split_index:].lstrip()

    return formatted_messages


def find_last_newline(message: str):
    last_newline = message.rfind('\n\n')
    if last_newline == -1:
        last_newline = message.rfind('.')
    return last_newline + 2


def getNameFormattedMessage(name) -> str:
    formatted_message = ""
    # Heading rather than a blockquote, for the same width reason as the hadith.
    formatted_message += f"### ✨ ({name.number}) - {name.name} - {name.transliteration}\n"
    formatted_message += f"{name.en['meaning']} - {name.en['desc']}\n"
    # Optional practical note on how/when to invoke this name in dua.
    dua = name.en.get("dua")
    if dua:
        formatted_message += f"\n🤲 **In your dua:** {dua}\n"
    return formatted_message


def resolve_start_position(
    existing: Optional[dict],
    start_book_id: Optional[int],
    start_chapter_id: Optional[int],
    start_hadith_id: Optional[int],
) -> tuple[int, int, int]:
    """Work out the (book, chapter, hadith) a channel should start from in setup.

    Blank book/chapter keep the channel's stored value (or 1 for a new channel).

    Chapter ids are global (each chapter belongs to one book), so changing the
    book without naming a chapter must not carry over the old book's chapter --
    we fall to 1, which at fetch time resolves to the new book's first chapter.

    For the hadith: an explicit ``start_hadith_id`` always wins. Otherwise, if
    the book or chapter is being changed, start at that chapter's *first* hadith
    -- represented as 1, which at fetch time resolves to the chapter's lowest
    ``id_in_book`` (the lookup is a ``>=`` scoped to the book+chapter). This
    avoids carrying over the stale hadith number, which could overshoot and skip
    past the chapter the admin just selected. If nothing positional changed,
    the current chapter and hadith are kept.
    """

    def keep(value, key, default):
        if value is not None:
            return value
        if existing is not None:
            return existing.get(key, default)
        return default

    book = keep(start_book_id, "last_book_id", 1)
    if start_chapter_id is not None:
        chapter = start_chapter_id
    elif start_book_id is not None:
        # Book changed without a chapter -> start at the new book's beginning.
        chapter = 1
    else:
        chapter = keep(None, "last_chapter_id", 1)
    if start_hadith_id is not None:
        hadith = start_hadith_id
    elif start_book_id is not None or start_chapter_id is not None:
        hadith = 1
    else:
        hadith = keep(None, "last_hadith_no", 1)
    return book, chapter, hadith


def delivery_failure_message(
    channel_label: str, guild_name: Optional[str] = None
) -> str:
    """What a server is told when the daily message can't be delivered.

    A 403 at 6pm is invisible from inside the server: the bot logs it and the
    hadiths just stop. Whoever reads this should not have to ask a follow-up
    question, so it spells out the clicks, how to confirm the fix, and how to
    turn the messages off instead.

    The steps are the ones from hadithbot.app/send-daily-hadith-discord, and
    they deliberately cover both ways this happens. When Send Messages is
    denied the bot is already listed under Roles/Members and you flip it back;
    when the channel is made private the bot isn't listed at all and step 2 is
    the one that matters. Adding a role that is already there is harmless, so
    one set of steps serves both rather than making the reader work out which
    case they are in.

    guild_name is included when this is sent as a DM, where the reader has no
    other way to tell which of their servers it's about.
    """
    where = f" in **{guild_name}**" if guild_name else ""
    return (
        f"Assalamu alaikum. I couldn't post today's hadith in "
        f"{channel_label}{where} because I no longer have permission to post "
        f"there.\n\n"
        f"To fix it:\n"
        f"1. Right-click the channel, then **Edit Channel**, then "
        f"**Permissions**\n"
        f"2. Under **Roles/Members**, press **+** and add HadithBot's role\n"
        f"3. Set **View Channel** and **Send Messages** to green\n"
        f"4. **Save Changes**, then run `/bismillah diagnose` to check it "
        f"worked\n\n"
        f"If the channel is synced to its category, set it on the category "
        f"instead. The longer version is at "
        f"<https://hadithbot.app/send-daily-hadith-discord>\n\n"
        f"If you'd rather I stopped posting there, run `/bismillah stop` in "
        f"that channel and you won't hear from me again."
    )
