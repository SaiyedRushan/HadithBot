"""Unit tests for the verse of the day: picking it, caching it, and posting it."""

import asyncio
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

import quran
from quran import Ayah, DailyAyah, ayah_on, format_ayah_messages, greeting, parse_ayah
from views import build_ayah_view

DAY = date(2026, 10, 29)


def make_ayah(surah=2, number=255, arabic="ٱللَّهُ لَآ إِلَٰهَ إِلَّا هُوَ", english=None):
    return Ayah(
        surah=surah,
        number=number,
        surah_name="Al-Baqarah",
        surah_meaning="The Cow",
        arabic=arabic,
        english=english
        or "Allah - there is no deity except Him, the Ever-Living, the Sustainer of [all] existence.",
    )


def payload(text_ar="بِسْمِ ٱللَّهِ", text_en="In the name of Allah, the Entirely Merciful."):
    surah = {"number": 1, "englishName": "Al-Faatiha", "englishNameTranslation": "The Opening"}
    return {
        "code": 200,
        "status": "OK",
        "data": [
            {
                "text": text_ar,
                "numberInSurah": 1,
                "surah": surah,
                "edition": {"identifier": "quran-uthmani"},
            },
            {
                "text": text_en,
                "numberInSurah": 1,
                "surah": surah,
                "edition": {"identifier": "en.sahih"},
            },
        ],
    }


class FakeFetch:
    """Stands in for alquran.cloud: answers from a dict, or raises."""

    def __init__(self, verses=None, fail=False):
        self.verses = verses or {}
        self.fail = fail
        self.calls: list[int] = []

    async def __call__(self, number: int) -> Ayah:
        self.calls.append(number)
        if self.fail:
            raise RuntimeError("down")
        return self.verses.get(number) or make_ayah(number=number)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# --- which verse ---------------------------------------------------------------


def test_same_day_same_verse_and_in_range():
    picks = {quran.pick_ayah_number(DAY) for _ in range(5)}
    assert len(picks) == 1
    assert 1 <= picks.pop() <= quran.TOTAL_AYAHS


def test_verse_changes_from_day_to_day():
    picks = {quran.pick_ayah_number(DAY + timedelta(days=i)) for i in range(30)}
    assert len(picks) > 25


def test_parse_reads_both_editions():
    ayah = parse_ayah(payload())
    assert ayah.key == "1:1"
    # Our spelling from data/114surahs.json, not alquran.cloud's "Al-Faatiha".
    assert ayah.surah_name == "Al-Fatihah"
    assert ayah.arabic == "بِسْمِ ٱللَّهِ"
    assert ayah.english.startswith("In the name of Allah")


def test_parse_rejects_an_error_response():
    with pytest.raises(ValueError):
        parse_ayah({"code": 404, "data": "Not found"})


# --- fetching once a day --------------------------------------------------------


def test_fetches_once_and_reuses_for_the_day():
    fetch = FakeFetch()
    daily = DailyAyah(fetch=fetch)

    async def main():
        return [await daily.for_day(DAY) for _ in range(4)]

    results = asyncio.run(main())
    assert len(fetch.calls) == 1
    assert len({r.key for r in results}) == 1


def test_a_new_day_fetches_a_new_verse():
    fetch = FakeFetch()
    daily = DailyAyah(fetch=fetch)
    asyncio.run(daily.for_day(DAY))
    asyncio.run(daily.for_day(DAY + timedelta(days=1)))
    assert len(fetch.calls) == 2


def test_a_verse_too_short_to_stand_alone_is_skipped_for_the_next():
    first = quran.pick_ayah_number(DAY)
    after = first % quran.TOTAL_AYAHS + 1
    fetch = FakeFetch({first: make_ayah(english="Alif, Lam, Meem.")})
    ayah = asyncio.run(DailyAyah(fetch=fetch).for_day(DAY))
    assert fetch.calls == [first, after]
    assert ayah is not None and ayah.number == after


def test_failure_returns_none_and_waits_before_asking_again():
    fetch = FakeFetch(fail=True)
    clock = FakeClock()
    daily = DailyAyah(fetch=fetch, clock=clock)

    assert asyncio.run(daily.for_day(DAY)) is None
    tried = len(fetch.calls)
    assert tried == quran.MAX_REQUESTS
    # The rest of the broadcast doesn't hammer a service that is down.
    assert asyncio.run(daily.for_day(DAY)) is None
    assert len(fetch.calls) == tried

    clock.now += quran.RETRY_AFTER_SECONDS + 1
    fetch.fail = False
    assert asyncio.run(daily.for_day(DAY)) is not None


# --- what gets posted -----------------------------------------------------------


def test_a_normal_verse_is_one_message():
    messages = format_ayah_messages(make_ayah())
    assert len(messages) == 1
    assert messages[0].startswith("### 📗 Quran 2:255 - Surah Al-Baqarah (The Cow)")
    assert "Saheeh International" in messages[0]
    # Square brackets are part of the translation, not markup to strip.
    assert "[all]" in messages[0]


def test_the_longest_verse_splits_into_two_that_each_fit():
    long = make_ayah(number=282, arabic="ا" * 1250, english="word " * 280)
    messages = format_ayah_messages(long)
    assert len(messages) == 2
    assert all(len(m) <= 2000 for m in messages)
    assert messages[0].startswith("### 📗 Quran 2:282")


def test_buttons_link_to_the_tafsir_quran_com_and_chatgpt():
    view = build_ayah_view(make_ayah())
    links = {b.label: b.url for b in view.children}
    assert links["Read tafsir"] == (
        "https://quran.com/2/255/tafsirs/en-tafisr-ibn-kathir"
    )
    assert links["Listen"] == "https://quran.com/2/255"
    question = parse_qs(urlparse(links["Ask ChatGPT"]).query)["q"][0]
    assert "verse 2:255 of the Quran" in question


def test_chatgpt_link_fits_a_button_even_for_a_long_verse():
    url = quran.chatgpt_url(make_ayah(english="word " * 280))
    assert len(url) <= 512
    assert "2%3A255" in url


def test_greeting_mentions_the_verse_only_when_there_is_one():
    assert "verse of the Quran" in greeting(True)
    assert "verse" not in greeting(False)


def test_on_unless_turned_off():
    assert ayah_on({"channel_id": "1"})
    assert ayah_on({"channel_id": "1", "ayah_enabled": True})
    assert not ayah_on({"channel_id": "1", "ayah_enabled": False})
