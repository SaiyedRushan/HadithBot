from typing import Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote
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


@dataclass
class Name:
    number: int
    name: str
    transliteration: str
    found: str
    en: Dict[str, str]
    fr: Dict[str, str]


def getHadithFormattedMessage(hadith) -> list[str]:
    formatted_messages = []
    formatted_messages.append(f"> ### Book: {hadith['books_metadata']['english_title']} - Chapter: {hadith['chapters']['english']}\n")
    # We deliberately don't show id_in_book here: it's a sequential per-book
    # counter that does NOT match sunnah.com's published reference numbers, so a
    # "#1000" would read as a citation a reader couldn't reproduce. The
    # Sunnah.com link button is the canonical pointer instead.
    formatted_hadith = f"> {hadith['english_narrator']} {hadith['english_text']}\n\n"
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
            formatted_hadith = f'> {formatted_hadith[split_index:].lstrip()}'

    return formatted_messages


def find_last_newline(message: str):
    last_newline = message.rfind('\n\n')
    if last_newline == -1:
        last_newline = message.rfind('.')
    return last_newline + 2


def getNameFormattedMessage(name) -> str:
    formatted_message = ""
    formatted_message += f"> ### ({name.number}) - {name.name} - {name.transliteration}\n"
    formatted_message += f"> {name.en['meaning']} - {name.en['desc']}\n"
    # Optional practical note on how/when to invoke this name in dua.
    dua = name.en.get("dua")
    if dua:
        formatted_message += f"> \n> 🤲 **In your dua:** {dua}\n"
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
