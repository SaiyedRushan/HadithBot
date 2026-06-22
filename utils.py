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
    return formatted_message
