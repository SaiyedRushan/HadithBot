import os
import random
import re
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

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
):
    supabase.table("discord_channel_state").upsert(
        {
            "channel_id": channel_id,
            "last_hadith_no": last_hadith_no,
            "last_name_no": last_name_no,
            "last_book_id": last_book_no,
            "last_chapter_id": last_chapter_no,
        },
        on_conflict="channel_id",
    ).execute()


def get_channels():
    return (
        supabase.table("discord_channel_state").select("*").eq("active", True).execute()
    )


def remove_channel_state(channel_id: str):
    supabase.table("discord_channel_state").delete().eq(
        "channel_id", channel_id
    ).execute()


def get_random_hadith():
    random_id = random.randint(1, 50884)
    res = (
        supabase.table("hadiths")
        .select("*, chapters(*), books_metadata(*)")
        .not_.is_("english_narrator", None)
        .gt("id", random_id)
        .order("id")
        .limit(1)
        .execute()
    )
    return res.data[0]


def get_hadith_by_hadith_no(
    hadith_no: int, book_no: int, chapter_no: int, count: int = 1
):
    res = (
        supabase.table("hadiths")
        .select("*, chapters(*), books_metadata(*)")
        .gte("id_in_book", hadith_no)
        .eq("book_id", book_no)
        .eq("chapter_id", chapter_no)
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
