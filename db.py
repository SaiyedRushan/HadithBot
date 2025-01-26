import os
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def save_channel_state(channel_id: str, last_hadith_no: int, last_name_no: int):
    supabase.table("discord_channel_state").upsert({
        "channel_id": channel_id,
        "last_hadith_no": last_hadith_no,
        "last_name_no": last_name_no
    }).execute()


def get_channels():
    return supabase.table("discord_channel_state").select("*").execute()

def remove_channel_state(channel_id: str):
    supabase.table("discord_channel_state").delete().eq("channel_id", channel_id).execute()

