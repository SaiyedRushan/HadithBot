"""The daily name match: name window, scoring replay, ranking and the card text."""

import json
from pathlib import Path

import pytest

import activity_token
import name_match as nm
from utils import Name

NAMES = [Name(**n) for n in json.loads(Path("data/99names.json").read_text())]


def items_for(last_sent, today=None):
    numbers = nm.pick_names(last_sent)
    return nm.build_items(NAMES, numbers, today if today is not None else [last_sent])


# --- which names ---------------------------------------------------------


@pytest.mark.parametrize(
    "last, expected",
    [(1, range(1, 11)), (9, range(1, 11)), (10, range(1, 11)), (58, range(49, 59)), (99, range(90, 100))],
)
def test_pick_names_is_the_ten_ending_at_the_last_sent(last, expected):
    assert nm.pick_names(last) == list(expected)


def test_no_window_has_two_cards_with_the_same_meaning():
    for last in range(1, 100):
        meanings = [p["right"].lower() for p in nm.all_pairs(items_for(last))]
        assert len(meanings) == len(set(meanings)), last


def test_items_hold_name_arabic_and_meaning():
    pair = nm.all_pairs(items_for(58))[-1]
    assert pair == {
        "id": 58,
        "left": "58. Al-Mubdi",
        "left_ar": NAMES[57].name,
        "right": "The Originator",
    }


# --- scoring -------------------------------------------------------------


def test_clean_run_scores_every_pair():
    items = items_for(58)
    score, results = nm.score_guesses(items, [[i, i] for i in range(49, 59)])
    assert score == 10 and results == [True] * 10


def test_a_wrong_guess_costs_both_pairs():
    items = items_for(58)
    guesses = [[52, 53]] + [[i, i] for i in range(49, 59)]
    score, results = nm.score_guesses(items, guesses)
    assert score == 8
    assert results[52 - 49] is False and results[53 - 49] is False


def test_stopping_early_leaves_unmatched_pairs_empty():
    score, results = nm.score_guesses(items_for(58), [[49, 49], [50, 51]])
    assert score == 1
    assert results == [True] + [None] * 9


def test_showing_a_pair_matches_it_and_costs_it():
    items = items_for(58)
    guesses = [["reveal", 52]] + [[i, i] for i in range(49, 59) if i != 52]
    score, results = nm.score_guesses(items, guesses)
    assert score == 9 and results[52 - 49] is False


def test_showing_a_matched_pair_or_a_stranger_is_rejected():
    for bad in ([[49, 49], ["reveal", 49]], [["reveal", 1]], [["reveal", "x"]]):
        with pytest.raises(nm.InvalidRun):
            nm.score_guesses(items_for(58), bad)


def test_a_matched_card_cannot_be_guessed_again():
    with pytest.raises(nm.InvalidRun):
        nm.score_guesses(items_for(58), [[49, 49], [49, 50]])


def test_a_card_from_outside_the_match_is_rejected():
    with pytest.raises(nm.InvalidRun):
        nm.score_guesses(items_for(58), [[1, 1]])


def test_malformed_guesses_are_rejected():
    for bad in (["x"], [[1]], [None], [["a", "b"]]):
        with pytest.raises(nm.InvalidRun):
            nm.score_guesses(items_for(58), bad)


def test_too_fast_is_rejected_and_silly_durations_dropped():
    results = [True] * 10
    with pytest.raises(nm.InvalidRun):
        nm.check_duration(4000, results)
    assert nm.check_duration(45000, results) == 45000
    assert nm.check_duration(None, results) is None
    assert nm.check_duration(10**9, results) is None


# --- ranking and rendering -----------------------------------------------


def run(uid, score, ms, created="2026-10-22T22:00:00", name=None, results=None):
    return {
        "discord_user_id": uid,
        "display_name": name or f"P{uid}",
        "score": score,
        "total": 10,
        "duration_ms": ms,
        "created_at": created,
        "item_results": results if results is not None else [True] * score + [False] * (10 - score),
    }


def test_rank_by_score_then_time_then_who_finished_first():
    ranked = nm.rank(
        [
            run("a", 9, 60000),
            run("b", 10, 90000),
            run("c", 9, 50000),
            run("d", 9, None),
            run("e", 9, 50000, created="2026-10-22T21:00:00"),
        ]
    )
    assert [r["discord_user_id"] for r in ranked] == ["b", "e", "c", "a", "d"]


@pytest.mark.parametrize(
    "ms, text", [(None, ""), (0, ""), (48000, "48s"), (65000, "1m 05s"), (3780000, "1h 03m")]
)
def test_format_duration(ms, text):
    assert nm.format_duration(ms) == text


def test_played_line():
    assert nm.played_line([]) == "Nobody has played yet."
    assert nm.played_line(["Rushan"]) == "**Rushan** played"
    assert nm.played_line(["A", "B"]) == "**A** and **B** played"
    assert nm.played_line(["A", "B", "C", "D"]) == "**A**, **B** and 2 others played"
    assert nm.played_line(["*x*"]) == "**\\*x\\*** played"


def test_streak_counts_days_in_a_row():
    keys = ["2026-10-22", "2026-10-21", "2026-10-20", "2026-10-18"]
    assert nm.group_streak(keys, "2026-10-22") == 3
    assert nm.streak_line(3) == "This server has played 3 days in a row 🔥"
    assert nm.streak_line(1) == ""


def day_row(last=58, today=None):
    return {"channel_id": "1", "day_key": "2026-10-22", "items": items_for(last, today)}


def test_empty_card():
    embed = nm.card_embed(day_row(), [])
    assert embed.title == "Today's name match: 10 names of Allah"
    assert embed.description == (
        "Match today's name, Al-Mubdi, and the 9 names before it to their meanings. "
        "Everyone in this server gets the same 10 and one try each. "
        "Scores appear in this message until tomorrow's hadith is posted."
        "\n\nNobody has played yet."
    )
    assert embed.footer.text == "Names 49 to 58 · The matching game comes from MugUp, mugup.app"


def test_card_with_players():
    results = [
        run("2", 9, 65000, name="Saif", results=[True] * 3 + [False] + [True] * 6),
        run("1", 10, 48000, name="Rushan"),
    ]
    embed = nm.card_embed(day_row(), results, played_keys=["2026-10-22", "2026-10-21"])
    parts = embed.description.split("\n\n")
    assert parts[1] == "This server has played 2 days in a row 🔥"
    assert parts[2] == "**Rushan** and **Saif** played"
    assert parts[3] == "**10/10** · 48s · <@1>\n" + "🟩" * 10
    assert parts[4] == "**9/10** · 1m 05s · <@2>\n🟩🟩🟩🟥🟩🟩🟩🟩🟩🟩"
    assert embed.footer.text.startswith(nm.LEGEND + "\n")


def test_two_names_today_and_the_start_of_the_list():
    two = nm.card_embed(day_row(58, [57, 58]), []).description
    assert two.startswith(
        "Match today's names, Al-Muhsi and Al-Mubdi, and the 8 names before them to their meanings."
    )
    start = nm.card_embed(day_row(1, [1]), []).description
    assert start.startswith(
        "Match names 1 to 10 to their meanings, including today's name, Ar-Rahman."
    )


def test_final_card_has_medals_and_counts_the_rest():
    results = [run(str(i), 10 - (i % 10), 40000 + i * 1000) for i in range(12)]
    embed = nm.card_embed(day_row(), results, final=True)
    assert embed.title == "Final results: name match for Thu 22 Oct"
    parts = embed.description.split("\n\n")
    assert parts[0] == "12 people played. Today's match is in the newest message from HadithBot."
    assert parts[1].startswith("🥇 **10/10**")
    assert parts[4].startswith("**4.** ")
    assert parts[-1] == "_and 2 other players_"


def test_final_card_nobody_played():
    embed = nm.card_embed(day_row(), [], final=True)
    assert embed.description == "Nobody played this one."


def test_no_em_dashes_anywhere_on_the_card():
    results = [run(str(i), i % 11, 40000 + i) for i in range(14)]
    for final in (False, True):
        embed = nm.card_embed(day_row(), results, final=final, played_keys=["2026-10-22"])
        text = (embed.title or "") + (embed.description or "") + (embed.footer.text or "")
        assert "—" not in text and "–" not in text


def test_board_rows_marks_me():
    rows = nm.board_rows([run("1", 7, 1000), run("2", 9, 1000)], me="1")
    assert [(r["rank"], r["isMe"]) for r in rows] == [(1, False), (2, True)]


# --- session token -------------------------------------------------------

SECRET = "x" * 40


def test_token_round_trip():
    token = activity_token.mint(SECRET, {"uid": "1", "cid": "2"}, now=1000)
    claims = activity_token.verify(SECRET, token, now=1001)
    assert claims["uid"] == "1" and claims["cid"] == "2"


def test_token_rejects_tampering_expiry_and_wrong_secret():
    token = activity_token.mint(SECRET, {"uid": "1"}, now=1000)
    version, payload, sig = token.split(".")
    forged = activity_token.mint("y" * 40, {"uid": "2"}, now=1000).split(".")[1]
    assert activity_token.verify(SECRET, f"{version}.{forged}.{sig}", now=1001) is None
    assert activity_token.verify(SECRET, token, now=1000 + activity_token.TTL_SECONDS + 1) is None
    assert activity_token.verify("z" * 40, token, now=1001) is None
    assert activity_token.verify(SECRET, "garbage", now=1001) is None
