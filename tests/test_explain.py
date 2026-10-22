"""Unit tests for the "Ask ChatGPT" button and the link it replies with."""

import re
from urllib.parse import parse_qs, urlparse

from utils import chatgpt_explain_url, compose_explain_reply
from views import ExplainHadithButton, build_hadith_view
from test_flagging import buttons, make_hadith


def prompt_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["q"][0]


def test_view_has_explain_button_with_hadith_id():
    view = build_hadith_view(make_hadith(hadith_id=40991))
    assert view is not None
    ids = [b.custom_id for b in buttons(view) if b.custom_id]
    assert "explain_hadith:40991" in ids
    assert "Ask ChatGPT" in [b.label for b in buttons(view)]


def test_explain_custom_id_round_trips():
    custom_id = ExplainHadithButton(123456).custom_id
    pattern = ExplainHadithButton.__discord_ui_compiled_template__.pattern
    match = re.fullmatch(pattern, custom_id)
    assert match and int(match["hadith_id"]) == 123456


def test_short_hadith_goes_in_whole_with_book_and_chapter():
    url, cut = chatgpt_explain_url(make_hadith(text="Actions are judged by intentions."))
    assert not cut
    assert url.startswith("https://chatgpt.com/?q=")
    prompt = prompt_of(url)
    assert "Sahih al-Bukhari" in prompt
    assert '"Revelation"' in prompt
    assert prompt.endswith("Narrated Abu Hurairah: Actions are judged by intentions.")


def test_long_hadith_is_cut_on_a_word_and_fits():
    # Longer than the longest hadith in the dataset (~9.7k chars).
    text = " ".join(f"word{i}" for i in range(2500))
    url, cut = chatgpt_explain_url(make_hadith(text=text))
    assert cut
    assert len(url) <= 3700
    prompt = prompt_of(url)
    assert prompt.endswith(" …")
    last_word = prompt[: -len(" …")].rsplit(" ", 1)[1]
    assert re.fullmatch(r"word\d+", last_word)


def test_non_ascii_text_counts_its_encoded_length():
    url, _ = chatgpt_explain_url(make_hadith(text="ﷺ " * 2000))
    assert len(url) <= 3700


def test_reply_fits_an_embed_and_says_when_cut():
    short = compose_explain_reply(make_hadith())
    long = compose_explain_reply(make_hadith(text="word " * 3000))
    assert len(long) <= 4096
    assert "too long" not in short
    assert "too long" in long
    assert "(https://chatgpt.com/?q=" in short
