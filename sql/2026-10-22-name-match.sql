-- Daily name match (name_match.py). Applied 2026-10-22 with
-- `supabase db query --linked -f`. RLS on with no policies: only the bot's
-- secret key reads or writes these, same as the other tables.

create table if not exists game_days (
  channel_id   text not null,
  day_key      date not null,          -- broadcast date in America/Toronto
  guild_id     text,
  game         text not null default 'names_10',
  items        jsonb not null,         -- frozen pairs, see name_match.build_items
  message_id   text,                   -- the card, set after it's posted
  played       boolean not null default false,
  posted_at    timestamptz not null default now(),
  closed_at    timestamptz,            -- set when the next broadcast finalises it
  primary key (channel_id, day_key)
);

create table if not exists game_results (
  id              bigint generated always as identity primary key,
  channel_id      text not null,
  day_key         date not null,
  guild_id        text,
  discord_user_id text not null,
  display_name    text not null,
  score           int  not null check (score >= 0),
  total           int  not null check (total > 0 and score <= total),
  item_results    jsonb not null,      -- [true|false|null] per pair, in pair order
  guesses         jsonb not null,      -- the raw guess log, for audits
  duration_ms     int  check (duration_ms > 0 and duration_ms <= 21600000),
  created_at      timestamptz not null default now(),
  unique (channel_id, day_key, discord_user_id),
  foreign key (channel_id, day_key) references game_days on delete cascade
);

create index if not exists game_results_board
  on game_results (channel_id, day_key, score desc, duration_ms asc);
create index if not exists game_days_played
  on game_days (channel_id, day_key desc) where played;

alter table game_days enable row level security;
alter table game_results enable row level security;

alter table discord_channel_state
  add column if not exists name_match_enabled boolean not null default true;
