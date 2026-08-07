"""Regenerate the books-and-chapters reference in docs/books.html.

The page lists every collection the bot draws from, and every chapter inside
it, with the ids an admin types into `/bismillah setup` (`start_book_id`,
`start_chapter_id`, `start_hadith_id`). The ids come from the database rather
than being retyped by hand, so the page can never drift from what the bot will
accept -- chapter ids in particular are neither consecutive nor global, and are
not something anyone should be transcribing.

Like update_site.py, only the fenced block is rewritten; the surrounding prose
is hand-written and never touched:

    <!-- books:start ... -->  ...  <!-- books:end -->

    make books                     # regenerate (needs SUPABASE_URL / SUPABASE_KEY)
    python update_books_page.py --check   # exit 1 if the page is out of date

The dataset is static, so this is a rerun-when-it-changes script, not something
CI needs on a schedule.
"""

import argparse
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "docs" / "books.html"

# Children of <div class="wrap"> sit at eight spaces in books.html.
IND = " " * 8

# Supabase caps a select at 1000 rows, so the wide tables are read in pages.
PAGE_SIZE = 1000


def fetch_all(table: str, columns: str, order: list[str]) -> list[dict]:
    """Every row of a table, walked a page at a time in a stable order."""
    from db import supabase

    rows: list[dict] = []
    start = 0
    while True:
        query = supabase.table(table).select(columns)
        for column in order:
            query = query.order(column)
        page = query.range(start, start + PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def collect() -> list[dict]:
    """Books, each with its chapters, hadith counts and hadith id ranges."""
    from db import supabase

    books = (
        supabase.table("books_metadata")
        .select("id, english_title, arabic_title, english_author")
        .order("id")
        .execute()
    ).data
    chapters = fetch_all("chapters", "id, book_id, english, arabic", ["book_id", "id"])

    # How many hadiths each chapter holds, and the span of `id_in_book` inside
    # it -- that span is exactly the range `start_hadith_id` accepts, so it's
    # worth the extra column here rather than leaving admins to guess.
    stats: dict[tuple[int, int], dict] = {}
    for hadith in fetch_all("hadiths", "book_id, chapter_id, id_in_book", ["id"]):
        key = (hadith["book_id"], hadith["chapter_id"])
        number = hadith["id_in_book"]
        entry = stats.get(key)
        if entry is None:
            stats[key] = {"count": 1, "first": number, "last": number}
        else:
            entry["count"] += 1
            entry["first"] = min(entry["first"], number)
            entry["last"] = max(entry["last"], number)

    by_book: dict[int, list[dict]] = {}
    for chapter in chapters:
        stat = stats.get((chapter["book_id"], chapter["id"]), {})
        by_book.setdefault(chapter["book_id"], []).append({**chapter, **stat})

    return [{**book, "chapters": by_book.get(book["id"], [])} for book in books]


def hadith_total(book: dict) -> int:
    return sum(c.get("count", 0) for c in book["chapters"])


def span(chapter: dict) -> str:
    """The chapter's hadith numbers, as a range (or a single number)."""
    first, last = chapter.get("first"), chapter.get("last")
    if first is None or last is None:
        return "—"
    return f"{first:,}" if first == last else f"{first:,}–{last:,}"


def render_overview(books: list[dict]) -> str:
    rows = "\n".join(
        f"{IND}      <tr>\n"
        f'{IND}        <td class="num">{book["id"]}</td>\n'
        f"{IND}        <td>\n"
        f'{IND}          <a href="#book-{book["id"]}">{escape(book["english_title"])}</a>\n'
        f'{IND}          <span class="sub">{escape(book["english_author"] or "")}</span>\n'
        f"{IND}        </td>\n"
        f'{IND}        <td class="num">{len(book["chapters"]):,}</td>\n'
        f'{IND}        <td class="num">{hadith_total(book):,}</td>\n'
        f"{IND}      </tr>"
        for book in books
    )
    return (
        f'{IND}<div class="table-scroll">\n'
        f'{IND}  <table class="books">\n'
        f"{IND}    <thead>\n"
        f"{IND}      <tr>\n"
        f'{IND}        <th scope="col">Book id</th>\n'
        f'{IND}        <th scope="col">Collection</th>\n'
        f'{IND}        <th scope="col">Chapters</th>\n'
        f'{IND}        <th scope="col">Hadiths</th>\n'
        f"{IND}      </tr>\n"
        f"{IND}    </thead>\n"
        f"{IND}    <tbody>\n{rows}\n{IND}    </tbody>\n"
        f"{IND}  </table>\n"
        f"{IND}</div>"
    )


def render_chapter(chapter: dict) -> str:
    arabic = (
        f'<span class="ar" lang="ar" dir="rtl">{escape(chapter["arabic"])}</span>'
        if chapter.get("arabic")
        else ""
    )
    return (
        f"{IND}        <tr>\n"
        f'{IND}          <td class="num id">{chapter["id"]}</td>\n'
        f"{IND}          <td>{escape(chapter['english'] or '—')}{arabic}</td>\n"
        f'{IND}          <td class="num">{chapter.get("count", 0):,}</td>\n'
        f'{IND}          <td class="num">{span(chapter)}</td>\n'
        f"{IND}        </tr>"
    )


def render_book(book: dict) -> str:
    rows = "\n".join(render_chapter(c) for c in book["chapters"])
    chapters = len(book["chapters"])
    arabic = (
        f'<span class="ar" lang="ar" dir="rtl">{escape(book["arabic_title"])}</span>'
        if book.get("arabic_title")
        else ""
    )
    return (
        f'{IND}<details class="book" id="book-{book["id"]}">\n'
        f"{IND}  <summary>\n"
        f'{IND}    <span class="chip">Book {book["id"]}</span>\n'
        f'{IND}    <span class="book-title">{escape(book["english_title"])}{arabic}</span>\n'
        f'{IND}    <span class="book-meta">'
        f"{chapters:,} chapter{'' if chapters == 1 else 's'} · "
        f"{hadith_total(book):,} hadiths</span>\n"
        f"{IND}  </summary>\n"
        f'{IND}  <div class="table-scroll">\n'
        f'{IND}    <table class="chapters">\n'
        f"{IND}      <thead>\n"
        f"{IND}        <tr>\n"
        f'{IND}          <th scope="col">Chapter id</th>\n'
        f'{IND}          <th scope="col">Chapter</th>\n'
        f'{IND}          <th scope="col">Hadiths</th>\n'
        f'{IND}          <th scope="col">Hadith ids</th>\n'
        f"{IND}        </tr>\n"
        f"{IND}      </thead>\n"
        f"{IND}      <tbody>\n{rows}\n{IND}      </tbody>\n"
        f"{IND}    </table>\n"
        f"{IND}  </div>\n"
        f"{IND}</details>"
    )


def render(books: list[dict]) -> str:
    parts = [render_overview(books)]
    parts.append(f'{IND}<h2 id="chapters">Every chapter, book by book</h2>')
    parts.append(
        f"{IND}<p>\n"
        f"{IND}  Open a collection to see its chapters. Chapter ids belong to their\n"
        f"{IND}  book — chapter 5 means something different in each — so always pass\n"
        f'{IND}  <span class="inline-code">start_book_id</span> alongside\n'
        f'{IND}  <span class="inline-code">start_chapter_id</span>.\n'
        f"{IND}</p>"
    )
    parts.append(f'{IND}<div class="toolbar">')
    parts.append(
        f'{IND}  <input id="q" type="search" class="search" autocomplete="off"\n'
        f'{IND}         placeholder="Search a collection or chapter — e.g. fasting"\n'
        f'{IND}         aria-label="Search collections and chapters" />\n'
        f'{IND}  <button type="button" class="ghost-btn" id="expandAll">Expand all</button>\n'
        f'{IND}  <button type="button" class="ghost-btn" id="collapseAll">Collapse all</button>'
    )
    parts.append(f"{IND}</div>")
    parts.append(f'{IND}<p class="result-count" id="results" hidden></p>')
    parts.extend(render_book(book) for book in books)
    return "\n".join(parts)


def replace_block(html: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:start.*?-->\n).*?(\n\s*<!-- {name}:end -->)", re.S)
    if not pattern.search(html):
        raise SystemExit(f"{PAGE}: no {name}:start / {name}:end block to fill")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), html, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="don't write; exit 1 if the page would change",
    )
    args = ap.parse_args()

    html = original = PAGE.read_text(encoding="utf-8")
    html = replace_block(html, "books", render(collect()))

    if html == original:
        print(f"{PAGE.relative_to(ROOT)} is already up to date")
        return 0
    if args.check:
        print(f"{PAGE.relative_to(ROOT)} is out of date -- run `make books`")
        return 1

    PAGE.write_text(html, encoding="utf-8")
    print(f"updated {PAGE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
