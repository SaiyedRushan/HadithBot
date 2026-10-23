-- More games in the daily match (name_match.GAMES): a score now says which
-- game it was for, and the one-try rule is one try per game per day.
-- Applied 2026-10-23 with `supabase db query --linked -f`. Rows from before
-- this are all the names game, which is the default.

alter table game_results
  add column if not exists game text not null default 'names';

alter table game_results
  drop constraint if exists game_results_channel_id_day_key_discord_user_id_key;

alter table game_results
  add constraint game_results_one_try_per_game
  unique (channel_id, day_key, discord_user_id, game);

drop index if exists game_results_board;
create index if not exists game_results_board
  on game_results (channel_id, day_key, game, score desc, duration_ms asc);
