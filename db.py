import os
import random
import logging
from datetime import datetime, timezone
from typing import Optional, cast
from supabase import create_client, Client
from dotenv import load_dotenv

from utils import BOT_REMOVED

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
    clear_stopped: bool = False,
    hadiths_per_day: Optional[int] = None,
    names_per_day: Optional[int] = None,
    channel_name: Optional[str] = None,
    guild_id: Optional[str] = None,
    guild_name: Optional[str] = None,
    guild_member_count: Optional[int] = None,
    mark_sent: bool = False,
    name_match_enabled: Optional[bool] = None,
):
    record = {
        "channel_id": channel_id,
        "last_hadith_no": last_hadith_no,
        "last_name_no": last_name_no,
        "last_book_id": last_book_no,
        "last_chapter_id": last_chapter_no,
    }
    # Only touch these when explicitly given. The daily progress-save omits some
    # so the upsert preserves the existing values; setup passes them in.
    # Setup on a stopped channel starts it again, at the position it kept.
    if clear_stopped:
        record["stopped_at"] = None
        record["stopped_reason"] = None
    if hadiths_per_day is not None:
        record["hadiths_per_day"] = hadiths_per_day
    if names_per_day is not None:
        record["names_per_day"] = names_per_day
    if name_match_enabled is not None:
        record["name_match_enabled"] = name_match_enabled
    # Human-readable labels so rows are identifiable at a glance. Refreshed on
    # every save (server/channel renames happen), hence not gated behind "new only".
    if channel_name is not None:
        record["channel_name"] = channel_name
    if guild_id is not None:
        record["guild_id"] = guild_id
    if guild_name is not None:
        record["guild_name"] = guild_name
    # How many people are in that server, as Discord reported it on the last
    # save. Refreshed alongside the names, so the site's headline count tracks
    # servers growing and shrinking rather than freezing at setup time. Discord
    # puts it in the guild payload, so it arrives without the Server Members
    # intent -- and without that intent it can lag reality by a few, which is
    # fine for a rounded figure on a marketing page and not fine for anything
    # that has to be exact.
    if guild_member_count is not None:
        record["guild_member_count"] = guild_member_count
    # Opt-in, because setup() saves through here too -- stamping unconditionally
    # would mark a freshly-configured channel as delivered and hide it from the
    # stale check until its first real send.
    # A delivery also settles any warning about the channel, so the owner is
    # told again straight away if it breaks later.
    if mark_sent:
        record["last_sent_at"] = datetime.now(timezone.utc).isoformat()
        record["warned_at"] = None
    supabase.table("discord_channel_state").upsert(
        record,
        on_conflict="channel_id",
    ).execute()


def get_channels() -> list[dict]:
    """Live channel states, for the daily broadcast. Supabase's stub types
    .data as the broad List[JSON]; in practice a select returns row dicts (empty
    if none), so we cast -- callers then get list[dict], not possibly-None rows.

    Excludes stopped channels (stopped_at set, for any reason). Those rows are
    kept, but nothing is sent to them, so counting them would overstate reach
    on the site and trying them would log a daily error for nothing."""
    return cast(
        list[dict],
        supabase.table("discord_channel_state")
        .select("*")
        .is_("stopped_at", "null")
        .execute()
        .data,
    )


def get_all_channels() -> list[dict]:
    """Every channel state, including paused ones and servers the bot has been
    removed from, for the /bismillah status command."""
    return cast(
        list[dict],
        supabase.table("discord_channel_state").select("*").execute().data,
    )


def get_known_guild_ids() -> set[str]:
    """Every guild_id with a stored channel, whether or not the bot is still
    in it. The startup reconcile compares this against the guilds Discord
    actually handed us."""
    rows = cast(
        list[dict],
        supabase.table("discord_channel_state").select("guild_id").execute().data,
    )
    return {r["guild_id"] for r in rows if r.get("guild_id")}


def mark_guild_removed(guild_id: str) -> int:
    """Stop every channel in a server the bot is no longer in.

    The rows survive untouched -- reading position, per-day counts -- so a
    server that re-adds the bot carries on from where it left off instead of
    restarting at hadith 1. Only channels still getting messages are touched:
    one that was deleted or stopped keeps that reason and its date.
    """
    res = (
        supabase.table("discord_channel_state")
        .update(
            {
                "stopped_at": datetime.now(timezone.utc).isoformat(),
                "stopped_reason": BOT_REMOVED,
            }
        )
        .eq("guild_id", guild_id)
        .is_("stopped_at", "null")
        .execute()
    )
    return len(res.data or [])


def mark_guild_present(guild_id: str) -> int:
    """Start a server's channels again once the bot is back in it. Only the
    ones stopped because the bot was removed: a deleted or stopped channel
    stays as it was."""
    res = (
        supabase.table("discord_channel_state")
        .update({"stopped_at": None, "stopped_reason": None})
        .eq("guild_id", guild_id)
        .eq("stopped_reason", BOT_REMOVED)
        .execute()
    )
    return len(res.data or [])


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


def set_warned(channel_id: str, field: str, warned: bool) -> None:
    """Record, or clear, when the owner was last told about a problem with
    this channel. field is warned_at (the hadith couldn't be posted) or
    embed_warned_at (the game card went out as plain text)."""
    value = datetime.now(timezone.utc).isoformat() if warned else None
    supabase.table("discord_channel_state").update({field: value}).eq(
        "channel_id", channel_id
    ).execute()


def stop_channel(channel_id: str, reason: str) -> int:
    """Stop the daily message in one channel, keeping its row. A channel that
    is already stopped keeps its first reason and date."""
    res = (
        supabase.table("discord_channel_state")
        .update(
            {
                "stopped_at": datetime.now(timezone.utc).isoformat(),
                "stopped_reason": reason,
            }
        )
        .eq("channel_id", channel_id)
        .is_("stopped_at", "null")
        .execute()
    )
    return len(res.data or [])


def save_hadith_flag(
    hadith_id: int,
    user_id: str,
    reason: Optional[str] = None,
    guild_id: Optional[str] = None,
    guild_name: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> None:
    """Record a reader's report that a hadith looks wrong.

    Upserted on (hadith_id, user_id) so a second flag from the same reader
    updates their note rather than piling up duplicate rows -- the count of
    flags on a hadith should mean "this many people", not "this many clicks".
    """
    supabase.table("hadith_flags").upsert(
        {
            "hadith_id": hadith_id,
            "user_id": user_id,
            "reason": reason,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "channel_id": channel_id,
            "resolved": False,
        },
        on_conflict="hadith_id,user_id",
    ).execute()


def count_hadith_flags(hadith_id: int) -> int:
    """How many distinct readers have an open flag on this hadith."""
    res = (
        supabase.table("hadith_flags")
        .select("id", count="exact")
        .eq("hadith_id", hadith_id)
        .eq("resolved", False)
        .execute()
    )
    return res.count or 0


def get_open_flags(limit: int = 20) -> list[dict]:
    """Unresolved flags, newest first, with enough of the hadith to judge them."""
    return cast(
        list[dict],
        supabase.table("hadith_flags")
        .select("*, hadiths(id, book_id, chapter_id, id_in_book, english_text)")
        .eq("resolved", False)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data,
    )


def get_flags_for_hadith(hadith_id: int) -> list[dict]:
    """Every flag on one hadith, resolved or not, for replying to the reporters."""
    return cast(
        list[dict],
        supabase.table("hadith_flags")
        .select("*, hadiths(id, book_id, chapter_id, id_in_book, english_text)")
        .eq("hadith_id", hadith_id)
        .order("created_at")
        .execute()
        .data,
    )


def resolve_hadith_flags(hadith_id: int) -> int:
    """Mark every open flag on a hadith as dealt with. Returns how many closed."""
    res = (
        supabase.table("hadith_flags")
        .update({"resolved": True})
        .eq("hadith_id", hadith_id)
        .eq("resolved", False)
        .execute()
    )
    return len(res.data or [])


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


def get_hadith_by_id(hadith_id: int) -> Optional[dict]:
    """One hadith with its book and chapter, for buttons on already-sent messages."""
    res = (
        supabase.table("hadiths")
        .select("*, chapters(*), books_metadata(*)")
        .eq("id", hadith_id)
        .limit(1)
        .execute()
    )
    return cast(dict, res.data[0]) if res.data else None


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


# --- daily name match (see name_match.py) ------------------------------------


def upsert_game_day(
    channel_id: str, day_key: str, guild_id: Optional[str], items: dict
) -> dict:
    """Today's match for a channel, created once.

    A second broadcast on the same day (/bismillah send-now) keeps the match
    people may already have played rather than replacing it.
    """
    existing = get_game_day(channel_id, day_key)
    if existing:
        return existing
    res = (
        supabase.table("game_days")
        .insert(
            {
                "channel_id": channel_id,
                "day_key": day_key,
                "guild_id": guild_id,
                "items": items,
            }
        )
        .execute()
    )
    return cast(dict, res.data[0])


def get_game_day(channel_id: str, day_key: str) -> Optional[dict]:
    res = (
        supabase.table("game_days")
        .select("*")
        .eq("channel_id", channel_id)
        .eq("day_key", day_key)
        .limit(1)
        .execute()
    )
    return cast(dict, res.data[0]) if res.data else None


def get_open_game_day(channel_id: str) -> Optional[dict]:
    """The newest match in a channel that hasn't been closed yet."""
    res = (
        supabase.table("game_days")
        .select("*")
        .eq("channel_id", channel_id)
        .is_("closed_at", "null")
        .order("day_key", desc=True)
        .limit(1)
        .execute()
    )
    return cast(dict, res.data[0]) if res.data else None


def get_open_game_days_before(channel_id: str, day_key: str) -> list[dict]:
    """Earlier matches in a channel that still need their final board."""
    return cast(
        list[dict],
        supabase.table("game_days")
        .select("*")
        .eq("channel_id", channel_id)
        .lt("day_key", day_key)
        .is_("closed_at", "null")
        .execute()
        .data,
    )


def set_game_day_message(channel_id: str, day_key: str, message_id: str) -> None:
    supabase.table("game_days").update({"message_id": message_id}).eq(
        "channel_id", channel_id
    ).eq("day_key", day_key).execute()


def close_game_day(channel_id: str, day_key: str) -> None:
    supabase.table("game_days").update(
        {"closed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("channel_id", channel_id).eq("day_key", day_key).execute()


def get_game_results(channel_id: str, day_key: str, game: str = "names") -> list[dict]:
    """Every score for one game of one day's match (see name_match.GAMES)."""
    return cast(
        list[dict],
        supabase.table("game_results")
        .select(
            "discord_user_id,display_name,score,total,item_results,duration_ms,created_at,game"
        )
        .eq("channel_id", channel_id)
        .eq("day_key", day_key)
        .eq("game", game)
        .execute()
        .data,
    )


def get_game_result(
    channel_id: str, day_key: str, user_id: str, game: str = "names"
) -> Optional[dict]:
    res = (
        supabase.table("game_results")
        .select(
            "discord_user_id,display_name,score,total,item_results,duration_ms,created_at,game"
        )
        .eq("channel_id", channel_id)
        .eq("day_key", day_key)
        .eq("discord_user_id", user_id)
        .eq("game", game)
        .limit(1)
        .execute()
    )
    return cast(dict, res.data[0]) if res.data else None


def insert_game_result(record: dict) -> tuple[dict, bool]:
    """Save a run. Returns (row, recorded); recorded is False when this player
    had already played this match, and the row is their first run."""
    try:
        res = supabase.table("game_results").insert(record).execute()
        return cast(dict, res.data[0]), True
    except Exception as e:
        # 23505: the unique (channel, day, player, game) constraint. One try
        # per game each day.
        if "23505" not in str(e) and "duplicate key" not in str(e):
            raise
    existing = get_game_result(
        record["channel_id"],
        record["day_key"],
        record["discord_user_id"],
        record.get("game", "names"),
    )
    if existing is None:
        raise RuntimeError("duplicate result reported but none found")
    return existing, False


def mark_game_day_played(channel_id: str, day_key: str) -> None:
    supabase.table("game_days").update({"played": True}).eq(
        "channel_id", channel_id
    ).eq("day_key", day_key).execute()


def get_played_day_keys(channel_id: str, limit: int = 400) -> list[str]:
    """Day keys on which anybody in this channel played, newest first.

    Read from game_days.played rather than the results, so a busy day with 40
    players counts once and the window still reaches back far enough for the
    streak."""
    rows = (
        supabase.table("game_days")
        .select("day_key")
        .eq("channel_id", channel_id)
        .eq("played", True)
        .order("day_key", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    return [str(r["day_key"]) for r in cast(list[dict], rows)]
