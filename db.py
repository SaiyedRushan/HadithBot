import os
import random
import logging
from typing import Optional, cast
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

if os.environ.get("SUPABASE_URL") is None:
    raise Exception("SUPABASE_URL is not set")
if os.environ.get("SUPABASE_KEY") is None:
    raise Exception("SUPABASE_KEY is not set")

url: str = os.environ.get("SUPABASE_URL") or ""
key: str = os.environ.get("SUPABASE_KEY") or ""
supabase: Client = create_client(url, key)


def save_channel_state(
    channel_id: str,
    last_hadith_no: int,
    last_name_no: int,
    last_book_no: int,
    last_chapter_no: int,
    active: Optional[bool] = None,
    hadiths_per_day: Optional[int] = None,
    names_per_day: Optional[int] = None,
):
    record = {
        "channel_id": channel_id,
        "last_hadith_no": last_hadith_no,
        "last_name_no": last_name_no,
        "last_book_id": last_book_no,
        "last_chapter_id": last_chapter_no,
    }
    # Only touch these when explicitly given. The daily progress-save omits them
    # so the upsert preserves the existing values; setup passes them in.
    if active is not None:
        record["active"] = active
    if hadiths_per_day is not None:
        record["hadiths_per_day"] = hadiths_per_day
    if names_per_day is not None:
        record["names_per_day"] = names_per_day
    supabase.table("discord_channel_state").upsert(
        record,
        on_conflict="channel_id",
    ).execute()


def get_channels() -> list[dict]:
    """Active channel states, for the daily broadcast. Supabase's stub types
    .data as the broad List[JSON]; in practice a select returns row dicts (empty
    if none), so we cast -- callers then get list[dict], not possibly-None rows."""
    return cast(
        list[dict],
        supabase.table("discord_channel_state")
        .select("*")
        .eq("active", True)
        .execute()
        .data,
    )


def get_all_channels() -> list[dict]:
    """Every channel state (active or paused), for the /bismillah status command."""
    return cast(
        list[dict],
        supabase.table("discord_channel_state").select("*").execute().data,
    )


def get_channel_state(channel_id: str):
    """The stored state for one channel, or None if it isn't set up yet."""
    res = (
        supabase.table("discord_channel_state")
        .select("*")
        .eq("channel_id", channel_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def remove_channel_state(channel_id: str):
    supabase.table("discord_channel_state").delete().eq(
        "channel_id", channel_id
    ).execute()


def get_books():
    """All books with their ids, for the /bismillah books reference command."""
    return (
        supabase.table("books_metadata")
        .select("id, english_title")
        .order("id")
        .execute()
    ).data


def get_chapters(book_id: int):
    """All chapters in a book with their ids, for /bismillah chapters."""
    return (
        supabase.table("chapters")
        .select("id, english")
        .eq("book_id", book_id)
        .order("id")
        .execute()
    ).data


# Largest hadith id, cached on first use. The dataset is static, so it never
# changes at runtime -- this avoids a hardcoded magic number and a second query
# on every call.
_max_hadith_id: Optional[int] = None


def _get_max_hadith_id() -> int:
    global _max_hadith_id
    cached = _max_hadith_id
    if cached is None:
        res = (
            supabase.table("hadiths")
            .select("id")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        cached = int(res.data[0]["id"]) if res.data else 0
        _max_hadith_id = cached
    return cached


def _random_hadith_query():
    return (
        supabase.table("hadiths")
        .select("*, chapters(*), books_metadata(*)")
        .neq("english_narrator", "")
        .neq("english_text", "")
        .order("id")
        .limit(1)
    )


def get_random_hadith():
    max_id = _get_max_hadith_id()
    if not max_id:
        return None
    random_id = random.randint(1, max_id)
    res = _random_hadith_query().gte("id", random_id).execute()
    if not res.data:
        # random_id landed past the last hadith with non-empty text; wrap to the first.
        res = _random_hadith_query().execute()
    return res.data[0] if res.data else None


def get_hadith_in_same_chapter_and_book(
    hadith_no: int, book_no: int, chapter_no: int, count: int = 1
):
    res = (
        supabase.table("hadiths")
        .select("*, chapters(*), books_metadata(*)")
        .gte("id_in_book", hadith_no)
        .eq("book_id", book_no)
        .eq("chapter_id", chapter_no)
        .order("book_id")
        .order("chapter_id")
        .order("id_in_book")
        .limit(count)
        .execute()
    )
    return res.data


def get_next_hadiths(hadith_no: int, book_no: int, chapter_no: int, count: int = 1):
    """Up to `count` hadiths in reading order starting at the given position.

    Unlike get_hadith_in_same_chapter_and_book, this crosses chapter and book
    boundaries: if the current chapter runs out mid-batch it keeps going into
    the next chapter/book, so the configured daily count is always honoured.
    Reading order is the global `id` column (same order used elsewhere, e.g.
    get_random_hadith)."""
    start = (
        supabase.table("hadiths")
        .select("id")
        .eq("id_in_book", hadith_no)
        .eq("book_id", book_no)
        .eq("chapter_id", chapter_no)
        .limit(1)
        .execute()
    )
    if not start.data:
        return []
    start_id = start.data[0]["id"]
    res = (
        supabase.table("hadiths")
        .select("*, chapters(*), books_metadata(*)")
        .gte("id", start_id)
        .order("id")
        .limit(count)
        .execute()
    )
    return res.data


def check_hadith_exists(hadith_no: int, book_no: int, chapter_no: int):
    res = (
        supabase.table("hadiths")
        .select("*")
        .eq("id_in_book", hadith_no)
        .eq("book_id", book_no)
        .eq("chapter_id", chapter_no)
        .execute()
    )
    return len(res.data) > 0


def get_next_available_chapter(book_id: int, current_chapter_id: int):
    res = (
        supabase.table("chapters")
        .select("id")
        .eq("book_id", book_id)
        .gt("id", current_chapter_id)
        .order("id")
        .limit(1)
        .execute()
    )
    return res.data[0]["id"] if res.data else None


def get_next_available_book(current_book_id: int):
    res = (
        supabase.table("books_metadata")
        .select("id")
        .gt("id", current_book_id)
        .order("id")
        .limit(1)
        .execute()
    )
    return res.data[0]["id"] if res.data else None


def find_valid_hadith_position(hadith_no: int, book_no: int, chapter_no: int):
    logger.debug(
        f"Checking if hadith {hadith_no} in book {book_no} chapter {chapter_no} is valid"
    )
    # Check if current position has a valid hadith
    if check_hadith_exists(hadith_no, book_no, chapter_no):
        logger.debug(
            f"Current hadith valid: book {book_no}, chapter {chapter_no}, hadith {hadith_no}"
        )
        return hadith_no, book_no, chapter_no

    logger.debug("Current hadith invalid: trying next hadith in current chapter")

    next_valid_hadith = get_hadith_in_same_chapter_and_book(
        hadith_no, book_no, chapter_no
    )
    if next_valid_hadith:
        logger.debug(
            f"Found next valid hadith: book {book_no} chapter {chapter_no} hadith {next_valid_hadith[0]['id_in_book']}"
        )
        book_no, chapter_no, hadith_no = (
            next_valid_hadith[0]["book_id"],
            next_valid_hadith[0]["chapter_id"],
            next_valid_hadith[0]["id_in_book"],
        )
        return hadith_no, book_no, chapter_no

    logger.debug("No next valid hadith found: trying next valid chapter")
    next_valid_chapter = get_next_available_chapter(book_no, chapter_no)
    if next_valid_chapter:
        next_valid_hadith = get_hadith_in_same_chapter_and_book(  # first hadith in next valid chapter, same book
            1, book_no, next_valid_chapter
        )
        if next_valid_hadith:
            logger.debug(
                f"Found next valid hadith in book {book_no} chapter {next_valid_chapter} hadith {next_valid_hadith[0]['id_in_book']}"
            )
            book_no, chapter_no, hadith_no = (
                next_valid_hadith[0]["book_id"],
                next_valid_hadith[0]["chapter_id"],
                next_valid_hadith[0]["id_in_book"],
            )
            return hadith_no, book_no, chapter_no

    logger.debug("No next valid chapter found: trying next valid book")
    next_valid_book = get_next_available_book(book_no)
    if next_valid_book:
        next_valid_chapter = get_next_available_chapter(next_valid_book, 0) or 0
        next_valid_hadith = get_hadith_in_same_chapter_and_book(
            1, next_valid_book, next_valid_chapter
        )  # first hadith in first chapter of next valid book
        if next_valid_hadith:
            logger.debug(
                f"Found next valid hadith in book {next_valid_book} chapter {next_valid_hadith[0]['chapter_id']} hadith {next_valid_hadith[0]['id_in_book']}"
            )
            book_no, chapter_no, hadith_no = (
                next_valid_hadith[0]["book_id"],
                next_valid_hadith[0]["chapter_id"],
                next_valid_hadith[0]["id_in_book"],
            )
            return hadith_no, book_no, chapter_no

    logger.debug("No next valid book found: wrapping around to beginning")
    book_no = 1
    chapter_no = 0
    hadith_no = 1

    return hadith_no, book_no, chapter_no
