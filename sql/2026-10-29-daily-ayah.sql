-- Verse of the day (quran.py). Off by default: a channel gets it only after
-- someone turns it on with `/bismillah setup quran_verse:True`.
-- Applied 2026-10-29 with `supabase db query --linked -f`, just before
-- deploying the code that uses it.

alter table discord_channel_state
  add column if not exists ayah_enabled boolean not null default false;
