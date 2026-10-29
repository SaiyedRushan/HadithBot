-- The verse of the day goes to every channel unless a server turns it off,
-- like the name match. Every existing row is switched on, stopped channels
-- included, so one that starts again gets what a new channel gets. Announced
-- in updates/2026-10-29.md, which explains `/bismillah setup quran_verse:False`.
-- Applied 2026-10-29 with `supabase db query --linked -f`.

begin;

alter table discord_channel_state
  alter column ayah_enabled set default true;

update discord_channel_state set ayah_enabled = true;

commit;
