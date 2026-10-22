"""The daily name match: which names it uses, how a run is scored, and the card.

The card is the last message of each daily batch. Its Play button opens the
Activity (the game in ``activity/``), and the card itself is the leaderboard:
it is re-rendered from all of the day's results whenever someone finishes, and
turned into a final board when the next broadcast goes out. The layout follows
MugUp's daily challenge card (``lib/discord/score-grid.ts`` and ``embeds.ts``
in that repo), minus its em dashes.

Pure on purpose, with no database import, so it can be tested without
credentials (same reasoning as views.py).
"""

from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence
from zoneinfo import ZoneInfo

import discord

MATCH_SIZE = 10
MAX_BOARD_ROWS = 10
EMBED_COLOR = 0xC8883A  # the site's accent colour
MUGUP_NAMES_URL = "https://mugup.app/decks/101"
MUGUP_CREDIT = "The matching game comes from MugUp, mugup.app"
LEGEND = "🟩 right on the first try · 🟥 took more than one try · ⬜ stopped before matching it"

# The daily broadcast runs at 6 PM Toronto time for every channel, so a match
# "day" is the Toronto date of the broadcast that posted it. It stays open
# until the next broadcast closes it.
DAY_TZ = ZoneInfo("America/Toronto")
NEXT_MATCH_TEXT = "tomorrow's hadith at 6:00 PM Eastern"

# A run faster than this per matched pair is not a person playing.
MIN_MS_PER_PAIR = 1000
MAX_DURATION_MS = 6 * 60 * 60 * 1000

MEDALS = ("🥇", "🥈", "🥉")


class InvalidRun(ValueError):
    """A submitted guess log that the game itself could never have produced."""


def day_key(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(DAY_TZ)
    return now.astimezone(DAY_TZ).date().isoformat()


def format_day(key: str) -> str:
    """``2026-10-21`` as ``Wed 21 Oct``."""
    d = date.fromisoformat(key)
    return f"{d:%a} {d.day} {d:%b}"


# --- which names -------------------------------------------------------------


def pick_names(last_sent: int, total: int = 99, size: int = MATCH_SIZE) -> list[int]:
    """The ``size`` consecutive name numbers ending at the last name sent today.

    A channel that hasn't reached name ``size`` yet gets names 1 to ``size``,
    which includes today's and a few it will meet soon. Names that share an
    English meaning (20 and 90, 58 and 95) are always further apart than
    ``size``, so a window never holds two cards with the same text.
    """
    last_sent = max(1, min(last_sent, total))
    if last_sent < size:
        return list(range(1, size + 1))
    return list(range(last_sent - size + 1, last_sent + 1))


def build_items(names: Sequence, numbers: Sequence[int], today: Sequence[int]) -> dict:
    """The frozen content of one day's match, stored on ``game_days.items``.

    ``names`` is the bot's full list of ``Name`` objects. Frozen at broadcast so
    a later edit to 99names.json can't change a match people already played.
    ``sets`` is a list so a second set (surahs) can be appended later; pair ids
    must stay unique across sets.
    """
    by_number = {n.number: n for n in names}
    pairs = []
    for number in numbers:
        n = by_number[number]
        pairs.append(
            {
                "id": n.number,
                "left": f"{n.number}. {n.transliteration}",
                "left_ar": n.name,
                "right": n.en["meaning"],
            }
        )
    today_names = [by_number[t].transliteration for t in today if t in by_number]
    return {
        "sets": [{"kind": "names", "pairs": pairs}],
        "today": list(today),
        "today_names": today_names,
    }


def all_pairs(items: dict) -> list[dict]:
    return [p for s in items["sets"] for p in s["pairs"]]


def set_sizes(items: dict) -> list[int]:
    return [len(s["pairs"]) for s in items["sets"]]


# --- scoring -----------------------------------------------------------------


def score_guesses(items: dict, guesses: Iterable) -> tuple[int, list[Optional[bool]]]:
    """Replay a run's guesses and score it the way the game does.

    A guess is ``[name_id, meaning_id]``. The same id is a match. Different ids
    mark both pairs as missed, so neither can score even once matched (MugUp's
    rule). ``["reveal", pair_id]`` is the game's "Show one pair" button: the
    pair is matched for the player and counts as missed. A pair scores when it
    was matched and never in a wrong guess or revealed.

    Returns ``(score, item_results)`` with one entry per pair in order: True
    (matched, no miss), False (matched after a miss), None (never matched).
    The game's own scoring (activity/src/game.ts) is the same.
    """
    pairs = all_pairs(items)
    ids = {p["id"] for p in pairs}
    matched: set[int] = set()
    missed: set[int] = set()
    count = 0
    for guess in guesses:
        count += 1
        if count > 1000:
            raise InvalidRun("too many guesses")
        if isinstance(guess, list) and len(guess) == 2 and guess[0] == "reveal":
            try:
                pid = int(guess[1])
            except (TypeError, ValueError):
                raise InvalidRun(f"malformed reveal {guess!r}") from None
            if pid not in ids:
                raise InvalidRun(f"reveal {guess!r} names a pair that isn't in this match")
            if pid in matched:
                raise InvalidRun(f"reveal {guess!r} is for a pair already matched")
            matched.add(pid)
            missed.add(pid)
            continue
        try:
            a, b = guess
            a, b = int(a), int(b)
        except (TypeError, ValueError):
            raise InvalidRun(f"malformed guess {guess!r}") from None
        if a not in ids or b not in ids:
            raise InvalidRun(f"guess {guess!r} names a card that isn't in this match")
        if a in matched or b in matched:
            raise InvalidRun(f"guess {guess!r} uses a card that was already matched")
        if a == b:
            matched.add(a)
        else:
            missed.update((a, b))

    results: list[Optional[bool]] = []
    for p in pairs:
        pid = p["id"]
        results.append(pid not in missed if pid in matched else None)
    return sum(1 for r in results if r is True), results


def check_duration(duration_ms, item_results: Sequence[Optional[bool]]) -> Optional[int]:
    """A sane duration in ms, or None when the client sent none.

    Raises InvalidRun for a run faster than a person could play it.
    """
    if duration_ms is None:
        return None
    try:
        ms = int(duration_ms)
    except (TypeError, ValueError):
        raise InvalidRun("duration is not a number") from None
    if ms <= 0 or ms > MAX_DURATION_MS:
        return None
    matched = sum(1 for r in item_results if r is not None)
    if ms < matched * MIN_MS_PER_PAIR:
        raise InvalidRun("run too fast to count")
    return ms


# --- ranking and rendering ---------------------------------------------------


def rank(results: Iterable[dict]) -> list[dict]:
    """Best first: score, then fastest (untimed last), then who finished first."""

    def key(r):
        ms = r.get("duration_ms")
        return (
            -int(r["score"]),
            ms is None,
            ms or 0,
            str(r.get("created_at") or ""),
            str(r.get("discord_user_id") or ""),
        )

    return sorted(results, key=key)


def format_duration(ms) -> str:
    """``48s``, ``1m 05s``, ``1h 03m``; empty for no time. Port of MugUp's."""
    if not isinstance(ms, (int, float)) or ms <= 0:
        return ""
    total = max(1, round(ms / 1000))
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def squares(item_results: Sequence[Optional[bool]], sizes: Sequence[int]) -> str:
    """One row of 🟩🟥⬜ per set."""
    glyph = {True: "🟩", False: "🟥", None: "⬜"}
    rows, i = [], 0
    for size in sizes:
        chunk = list(item_results[i : i + size])
        chunk += [None] * (size - len(chunk))
        rows.append("".join(glyph[r] for r in chunk))
        i += size
    return "\n".join(rows)


def _clean_name(name: str) -> str:
    return discord.utils.escape_markdown(discord.utils.escape_mentions(name or "Someone"))


def played_line(display_names: Sequence[str]) -> str:
    names = [f"**{_clean_name(n)}**" for n in display_names]
    if not names:
        return "Nobody has played yet."
    if len(names) == 1:
        return f"{names[0]} played"
    if len(names) == 2:
        return f"{names[0]} and {names[1]} played"
    if len(names) == 3:
        return f"{names[0]}, {names[1]} and {names[2]} played"
    return f"{names[0]}, {names[1]} and {len(names) - 2} others played"


def group_streak(played_keys: Iterable[str], end_key: str) -> int:
    """Days in a row, ending at ``end_key``, on which somebody here played."""
    played = set(played_keys)
    streak, cursor = 0, date.fromisoformat(end_key)
    for _ in range(3650):
        if cursor.isoformat() not in played:
            break
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def streak_line(streak: int) -> str:
    if streak < 2:
        return ""
    return f"This server has played {streak} days in a row 🔥"


def player_block(result: dict, sizes: Sequence[int], prefix: str = "") -> str:
    took = format_duration(result.get("duration_ms"))
    line = f"**{result['score']}/{result['total']}**"
    if took:
        line += f" · {took}"
    line += f" · <@{result['discord_user_id']}>"
    return f"{prefix}{line}\n{squares(result.get('item_results') or [], sizes)}"


def intro_text(items: dict) -> str:
    pairs = all_pairs(items)
    first, last = pairs[0]["id"], pairs[-1]["id"]
    today = items.get("today") or []
    names = items.get("today_names") or []
    if len(names) == 1:
        named = f"today's name, {names[0]},"
        ref = "it"
    elif len(names) == 2:
        named = f"today's names, {names[0]} and {names[1]},"
        ref = "them"
    elif names:
        named = f"today's names, {', '.join(names[:-1])} and {names[-1]},"
        ref = "them"
    else:
        named, ref = "", ""
    before = len(pairs) - len(names)
    if names and today and max(today) == last and before > 0:
        opening = f"Match {named} and the {before} names before {ref} to their meanings."
    elif names:
        opening = f"Match names {first} to {last} to their meanings, including {named.rstrip(',')}."
    else:
        opening = f"Match names {first} to {last} to their meanings."
    return (
        f"{opening} Everyone in this server gets the same {len(pairs)} and one try each. "
        "Scores appear in this message until tomorrow's hadith is posted."
    )


def card_title(items: dict) -> str:
    return f"Today's name match: {len(all_pairs(items))} names of Allah"


def card_embed(
    day: dict,
    results: Sequence[dict],
    *,
    final: bool = False,
    played_keys: Iterable[str] = (),
) -> discord.Embed:
    """The card for one day. ``day`` is a ``game_days`` row."""
    items = day["items"]
    sizes = set_sizes(items)
    pairs = all_pairs(items)
    ranked = rank(results)
    shown, hidden = ranked[:MAX_BOARD_ROWS], len(ranked) - MAX_BOARD_ROWS

    parts: list[str] = []
    if final:
        title = f"Final results: name match for {format_day(day['day_key'])}"
        if not ranked:
            parts.append("Nobody played this one.")
        else:
            people = "1 person" if len(ranked) == 1 else f"{len(ranked)} people"
            parts.append(f"{people} played. Today's match is in the newest message from HadithBot.")
        for i, r in enumerate(shown):
            prefix = f"{MEDALS[i]} " if i < len(MEDALS) else f"**{i + 1}.** "
            parts.append(player_block(r, sizes, prefix))
    else:
        title = card_title(items)
        parts.append(intro_text(items))
        line = streak_line(group_streak(played_keys, day["day_key"]))
        if line:
            parts.append(line)
        parts.append(played_line([r.get("display_name") or "" for r in ranked]))
        for r in shown:
            parts.append(player_block(r, sizes))
    if hidden > 0:
        parts.append(f"_and {hidden} other player{'s' if hidden != 1 else ''}_")

    embed = discord.Embed(title=title, description="\n\n".join(parts)[:4096], color=EMBED_COLOR)
    footer = f"Names {pairs[0]['id']} to {pairs[-1]['id']} · {MUGUP_CREDIT}"
    if ranked:
        footer = f"{LEGEND}\n{footer}"
    embed.set_footer(text=footer)
    return embed


def board_rows(results: Sequence[dict], me: Optional[str] = None) -> list[dict]:
    """The board as the Activity shows it."""
    return [
        {
            "rank": i + 1,
            "displayName": r.get("display_name") or "Someone",
            "score": r["score"],
            "total": r["total"],
            "durationMs": r.get("duration_ms"),
            "isMe": me is not None and str(r.get("discord_user_id")) == str(me),
        }
        for i, r in enumerate(rank(results)[:25])
    ]


def result_payload(r: dict) -> dict:
    return {
        "score": r["score"],
        "total": r["total"],
        "itemResults": r.get("item_results") or [],
        "durationMs": r.get("duration_ms"),
    }
