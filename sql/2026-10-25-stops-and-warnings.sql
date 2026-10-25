-- One way to record that a channel no longer gets the daily message, in
-- place of three (active = false, removed_at, and deleting the row).
-- stopped_at decides it: the broadcast sends only where it is null.
-- stopped_reason says why, and the two are always set or cleared together.
-- Rows are never deleted any more.
--
--   bot_removed       the bot was kicked or banned, or the server was deleted;
--                     cleared by itself when the bot is added back
--   channel_deleted   Discord says the channel no longer exists
--   stopped_by_admin  someone ran /bismillah stop (or switched it off by hand)
--
-- Applied 2026-10-25 with `supabase db query --linked -f`, just before
-- deploying the code that uses it. active and
-- removed_at stay for now so the running bot keeps working; a later
-- migration drops them.

begin;

alter table discord_channel_state
  add column if not exists stopped_at timestamptz,
  add column if not exists stopped_reason text;

alter table discord_channel_state
  add constraint stopped_reason_known
    check (stopped_reason in ('bot_removed', 'channel_deleted', 'stopped_by_admin')),
  add constraint stopped_set_together
    check ((stopped_at is null) = (stopped_reason is null));

-- Servers the bot is out of keep the date it was first noticed.
update discord_channel_state
set stopped_at = removed_at, stopped_reason = 'bot_removed'
where removed_at is not null and stopped_at is null;

-- The two Ayo Ngaji channels Discord returns 404 for (switched off by hand
-- on 2026-10-25). Last delivered 2026-09-21; when they were deleted isn't
-- recorded, so the date is when this was applied.
update discord_channel_state
set stopped_at = now(), stopped_reason = 'channel_deleted'
where channel_id in ('1551236475192877056', '1551247888154234962')
  and stopped_at is null;

-- Anything else switched off by hand (Dev #hadithbot on 2026-10-25).
update discord_channel_state
set stopped_at = now(), stopped_reason = 'stopped_by_admin'
where not active and stopped_at is null;

-- When a server's owner was last told about a problem with this channel, so
-- they're told at most once a week while it lasts. These used to live in the
-- bot's memory, which a restart wiped, so every deploy meant another notice
-- that evening. warned_at: the hadith couldn't be posted (cleared when it
-- is). embed_warned_at: the game card went out as plain text because the bot
-- has no Embed Links (cleared when it goes out as an embed again).
alter table discord_channel_state
  add column if not exists warned_at timestamptz,
  add column if not exists embed_warned_at timestamptz;

-- Bangladesh/BD's owner was DMed about Embed Links by hand on 2026-10-25.
update discord_channel_state
set embed_warned_at = now()
where channel_id = '1546586966580273162';

commit;
