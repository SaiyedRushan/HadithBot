-- Drop the two columns stopped_at and stopped_reason replaced
-- (2026-10-25-stops-and-warnings.sql). Nothing has read or written them since
-- 3ceac7b, and the first broadcast on that code (2026-10-25) delivered to every
-- channel. Dropping active also drops its index on (active, last_sent_at).
-- Applied 2026-10-26 with `supabase db query --linked -f`.

alter table discord_channel_state
  drop column active,
  drop column removed_at;
