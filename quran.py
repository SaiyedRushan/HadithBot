"""The daily verse of the Quran: which verse, fetching it, and how it is posted.

There is no Quran table in the database. Each day's verse comes from
alquran.cloud, fetched once and kept in memory, so every channel gets the same
verse for one request. The verse is picked from the date, so a restart (or a
/bismillah send-now later in the day) fetches the same one again rather than a
different one.

Nothing here touches the database, so tests can import it without credentials.
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable, Optional
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger("HadithBot")

TOTAL_AYAHS = 6236
# Uthmani script plus Saheeh International, in one request. Keep the square
# brackets in the translation: they mark words the translators added.
_API = "https://api.alquran.cloud/v1/ayah/{number}/editions/quran-uthmani,en.sahih"
TRANSLATION = "Saheeh International"

# Verses whose translation is this short are things like "Alif, Lam, Meem." or
# "By the dawn", which mean little posted on their own; the next verse is used
# instead.
MIN_ENGLISH = 30
# Requests per day at most: covers a short verse or two, or a failed request.
MAX_REQUESTS = 3
# After a failed day, wait this long before asking the API again, so a broadcast
# to every channel makes one attempt rather than one per channel.
RETRY_AFTER_SECONDS = 10 * 60

# Surah names as the surah match game spells them ("Al-Fatihah", not
# alquran.cloud's "Al-Faatiha"), by surah number.
_SURAHS = {
    s["number"]: s
    for s in json.loads(
        (Path(__file__).resolve().parent / "data" / "114surahs.json").read_text()
    )
}

_MESSAGE_LIMIT = 2000  # Discord's per-message character cap
_BUTTON_URL_LIMIT = 500  # safely under Discord's 512-char button-URL limit


@dataclass(frozen=True)
class Ayah:
    surah: int
    number: int  # the verse's number within its surah
    surah_name: str  # "Al-Baqara"
    surah_meaning: str  # "The Cow"
    arabic: str
    english: str

    @property
    def key(self) -> str:
        return f"{self.surah}:{self.number}"


def pick_ayah_number(day: date) -> int:
    """The verse for ``day``, numbered 1 to 6236 across the whole Quran.

    Seeded with the date, so it is the same on every call that day and
    changes the next. A str seed is hashed the same way on every run, unlike
    hash().
    """
    return random.Random(f"ayah:{day.isoformat()}").randint(1, TOTAL_AYAHS)


def parse_ayah(payload: dict) -> Ayah:
    """An Ayah from alquran.cloud's two-edition response. Raises on any other shape."""
    if payload.get("code") != 200:
        raise ValueError(f"alquran.cloud said {payload.get('code')}: {payload.get('data')}")
    editions = {e["edition"]["identifier"]: e for e in payload["data"]}
    arabic = editions["quran-uthmani"]
    english = editions["en.sahih"]
    surah = arabic["surah"]
    ours = _SURAHS.get(int(surah["number"]), {})
    return Ayah(
        surah=int(surah["number"]),
        number=int(arabic["numberInSurah"]),
        surah_name=ours.get("transliteration") or surah["englishName"],
        surah_meaning=ours.get("meaning") or surah["englishNameTranslation"],
        arabic=" ".join(arabic["text"].split()),
        english=" ".join(english["text"].split()),
    )


async def fetch_ayah(number: int) -> Ayah:
    """One verse, by its number across the whole Quran (1 to 6236)."""
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(_API.format(number=number)) as r:
            if r.status != 200:
                raise RuntimeError(f"alquran.cloud returned {r.status} for verse {number}")
            return parse_ayah(await r.json())


class DailyAyah:
    """Today's verse, fetched on first use and then kept for the rest of the day."""

    def __init__(
        self,
        fetch: Callable[[int], Awaitable[Ayah]] = fetch_ayah,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._fetch = fetch
        self._clock = clock
        self._day: Optional[date] = None
        self._ayah: Optional[Ayah] = None
        self._failed_at: Optional[float] = None

    async def for_day(self, day: date) -> Optional[Ayah]:
        """The verse for ``day``, or None if alquran.cloud can't be reached.

        Never raises: a missing verse must not stop the hadith going out.
        """
        if day == self._day:
            if self._ayah is not None:
                return self._ayah
            if (
                self._failed_at is not None
                and self._clock() - self._failed_at < RETRY_AFTER_SECONDS
            ):
                return None

        number = pick_ayah_number(day)
        found: Optional[Ayah] = None
        for _ in range(MAX_REQUESTS):
            try:
                ayah = await self._fetch(number)
            except Exception as e:
                logger.warning(f"Couldn't fetch verse {number} from alquran.cloud: {e}")
                continue
            found = ayah
            if len(ayah.english) >= MIN_ENGLISH:
                break
            # Too short to stand alone; try the verse after it.
            number = number % TOTAL_AYAHS + 1

        self._day = day
        self._ayah = found
        self._failed_at = None if found else self._clock()
        if found is None:
            logger.error(f"No verse of the day for {day}: alquran.cloud didn't answer")
        return found


def tafsir_url(ayah: Ayah) -> str:
    """Ibn Kathir's tafsir of this verse on Quran.com (the page can switch tafsir)."""
    return f"https://quran.com/{ayah.surah}/{ayah.number}/tafsirs/en-tafisr-ibn-kathir"


def quran_com_url(ayah: Ayah) -> str:
    """The verse on Quran.com, where it can be played aloud."""
    return f"https://quran.com/{ayah.surah}/{ayah.number}"


def chatgpt_url(ayah: Ayah) -> str:
    """A chatgpt.com link with a question about this verse already typed in.

    Unlike a hadith, a verse has one reference everyone agrees on, so the
    reference alone tells ChatGPT which verse. The translation goes in too when
    the link has room, as a check that it is talking about the right one.
    """
    head = (
        f"Please explain verse {ayah.key} of the Quran (Surah {ayah.surah_name}). "
        "What does it mean, and what do classical tafsirs such as Ibn Kathir say about it?"
    )
    with_text = "https://chatgpt.com/?" + urlencode(
        {"q": f'{head}\n\n{TRANSLATION}: "{ayah.english}"'}
    )
    if len(with_text) <= _BUTTON_URL_LIMIT:
        return with_text
    return "https://chatgpt.com/?" + urlencode({"q": head})


def format_ayah_messages(ayah: Ayah) -> list[str]:
    """The verse as Discord messages: one, or two for the longest verses."""
    heading = (
        f"### 📗 Quran {ayah.key} - Surah {ayah.surah_name} ({ayah.surah_meaning})\n"
    )
    arabic = f"{ayah.arabic}\n"
    english = f"{ayah.english}\n-# Translation: {TRANSLATION}"
    whole = f"{heading}{arabic}\n{english}"
    if len(whole) <= _MESSAGE_LIMIT:
        return [whole]
    # The longest verse (2:282) is about 1,200 characters in Arabic and 1,300
    # in English, so each half fits in a message of its own.
    return [_fit(heading + arabic), _fit(english)]


def _fit(text: str) -> str:
    if len(text) <= _MESSAGE_LIMIT:
        return text
    return text[: _MESSAGE_LIMIT - 1].rstrip() + "…"


def greeting(with_ayah: bool) -> str:
    """The line that opens each day's messages, naming what follows."""
    if with_ayah:
        return (
            "# Assalamu Alaikum Warahmatullahi Wabarakatuh, here is today's verse "
            "of the Quran, today's hadith and one of Allah's beautiful names\n"
        )
    return (
        "# Assalamu Alaikum Warahmatullahi Wabarakatuh, here is today's hadith "
        "and one of Allah's beautiful names\n"
    )


def ayah_on(channel_row: dict) -> bool:
    """On unless the channel turned it off with /bismillah setup quran_verse:False."""
    return channel_row.get("ayah_enabled") is not False
