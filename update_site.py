"""Regenerate the two generated blocks in docs/index.html: the usage stats and
the community wall.

Both blocks are fenced by HTML comments in the page and rewritten in place, so
the rest of the hand-written markup is never touched:

    <!-- stats:start ... -->  ...  <!-- stats:end -->
    <!-- communities:start ... -->  ...  <!-- communities:end -->

The stats are aggregate counts read from the live database -- how many servers
and channels, and how many messages go out a day. No server is named by them.

The wall is rendered from docs/data/communities.json, which is hand-curated:
a community is listed only once one of its admins has asked to be. The database
knows every server the bot is in, and that is deliberately not what feeds this.

    make site                  # both blocks (needs SUPABASE_URL / SUPABASE_KEY)
    python update_site.py --no-stats   # wall only, no database needed
    python update_site.py --check      # exit 1 if the page is out of date
"""

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "docs" / "index.html"
COMMUNITIES = ROOT / "docs" / "data" / "communities.json"

ADD_YOURS_URL = "https://github.com/SaiyedRushan/HadithBot/issues/new?template=add-community.yml"

# Children of <div class="wrap"> sit at ten spaces in index.html.
IND = " " * 10

# Skipped when deriving a monogram, so "York University MSA" gives YU and
# "The Deen Society" gives DS.
MINOR_WORDS = {"the", "of", "at", "and", "for", "a", "an"}


def read_communities() -> list[dict]:
    data = json.loads(COMMUNITIES.read_text(encoding="utf-8"))
    return data["communities"]


def monogram(name: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    major = [w for w in words if w.lower() not in MINOR_WORDS] or words
    return "".join(w[0] for w in major[:2]).upper()


def collect_stats() -> list[tuple[str, str]]:
    """(value, label) pairs for the stat row, from the live database."""
    # Imported here rather than at module scope so --no-stats works without any
    # database credentials -- db.py raises on import when they're missing.
    from db import get_channels

    rows = get_channels()
    guilds = {r["guild_id"] for r in rows if r.get("guild_id")}
    unlabelled = sum(1 for r in rows if not r.get("guild_id"))
    if unlabelled:
        print(
            f"note: {unlabelled} active channel(s) have no guild_id and are not "
            "counted as servers -- run backfill_channel_names.py to fill them in"
        )

    per_day = sum((r.get("hadiths_per_day") or 0) + (r.get("names_per_day") or 0) for r in rows)

    stats = [
        (f"{len(guilds):,}", "server" if len(guilds) == 1 else "servers"),
        (f"{len(rows):,}", "channel" if len(rows) == 1 else "channels"),
        (f"{per_day:,}", "reminders a day"),
    ]

    # Oldest channel row, as a "running since" tile. Older rows predate the
    # column, so this is best-effort and simply dropped when unavailable.
    started = min(
        (r["created_at"] for r in rows if r.get("created_at")),
        default=None,
    )
    if started:
        month = (
            "January February March April May June July August September October November December"
        ).split()[int(started[5:7]) - 1]
        stats.append((f"{month[:3]} {started[:4]}", "running since"))

    return stats


def render_stats(stats: list[tuple[str, str]]) -> str:
    rows = "\n".join(
        f'{IND}  <div class="stat"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for value, label in stats
    )
    return f'{IND}<div class="stats">\n{rows}\n{IND}</div>'


def render_community(c: dict) -> str:
    name = c["name"]
    url = c.get("url")
    logo = c.get("logo")

    tag = "a" if url else "div"
    attrs = f' href="{escape(url, quote=True)}" target="_blank" rel="noopener"' if url else ""
    crest = (
        f'<span class="crest"><img src="{escape(logo, quote=True)}" alt="" '
        f'width="44" height="44" loading="lazy" decoding="async" /></span>'
        if logo
        else f'<span class="crest" aria-hidden="true">'
        f"{escape(c.get('initials') or monogram(name))}</span>"
    )
    place = (
        f'\n{IND}      <span class="community-place">{escape(c["location"])}</span>'
        if c.get("location")
        else ""
    )

    return (
        f'{IND}  <{tag} class="community"{attrs}>\n'
        f"{IND}    {crest}\n"
        f'{IND}    <span class="community-text">\n'
        f'{IND}      <span class="community-name">{escape(name)}</span>{place}\n'
        f"{IND}    </span>\n"
        f"{IND}  </{tag}>"
    )


def render_wall(communities: list[dict]) -> str:
    cards = [render_community(c) for c in communities]
    cards.append(
        f'{IND}  <a class="community community-add" href="{ADD_YOURS_URL}"\n'
        f'{IND}     target="_blank" rel="noopener">\n'
        f'{IND}    <span class="crest" aria-hidden="true">+</span>\n'
        f'{IND}    <span class="community-text">\n'
        f'{IND}      <span class="community-name">Your MSA here</span>\n'
        f'{IND}      <span class="community-place">Ask to be added</span>\n'
        f"{IND}    </span>\n"
        f"{IND}  </a>"
    )
    inner = "\n".join(cards)
    return f'{IND}<div class="community-wall">\n{inner}\n{IND}</div>'


def replace_block(html: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:start.*?-->\n).*?(\n\s*<!-- {name}:end -->)", re.S)
    if not pattern.search(html):
        raise SystemExit(f"{PAGE}: no {name}:start / {name}:end block to fill")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), html, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--no-stats",
        action="store_true",
        help="only re-render the community wall; leave the stats as they are",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="don't write; exit 1 if the page would change",
    )
    args = ap.parse_args()

    html = original = PAGE.read_text(encoding="utf-8")
    html = replace_block(html, "communities", render_wall(read_communities()))
    if not args.no_stats:
        html = replace_block(html, "stats", render_stats(collect_stats()))

    if html == original:
        print(f"{PAGE.relative_to(ROOT)} is already up to date")
        return 0
    if args.check:
        print(f"{PAGE.relative_to(ROOT)} is out of date -- run `make site`")
        return 1

    PAGE.write_text(html, encoding="utf-8")
    print(f"updated {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
