# Daily name match: a MugUp-style pair game inside HadithBot

## TL;DR

- **What it is:** every daily batch ends with one new message, "Today's name match: 10 names of Allah", with a **Play today's match** button. It opens a Discord Activity: MugUp's 20-card pair grid, 10 names to 10 meanings, one try per person per day.
- **Which 10 names:** today's name plus the 9 before it in that channel (names 1 to 10 for a channel that's just starting). Everyone in the server gets the same 10.
- **Leaderboard:** that same message, edited after every finished run, in MugUp's daily-card layout: who played, then `**9/10** · 1m 05s · @name` and one row of 🟩🟥⬜ squares. Sorted by score, then time.
- **End of day:** the next 6 PM broadcast edits yesterday's card into "Final results" with medals and removes its Play button. No cron, no separate results post.
- **Soft MugUp promotion:** a grey **All 99 names on MugUp** link button on the message (to mugup.app/decks/101), a footer line, and one card on the results screen. Nothing in the way of playing.
- **Where the code lives:** the game screen is a small React app in a new `activity/` folder, hosted on Vercel. The API (sign-in, today's match, posting a score) runs inside the bot's existing aiohttp server, so the bot edits its own messages and the scoring/rendering is Python with pytest.
- **Ported from MugUp, copied not shared:** the pair grid, timer and pick logic (`PairMatchGamePlay.tsx`), the SDK sign-in, the signed session token, and the ranking and score-grid rendering.
- **Later (v2):** a second set in the same match, 10 surahs, scored out of 20, one row of squares per set.
- **Mockup of every screen:** [plans/name-match-mockup.html](name-match-mockup.html).

**You have to do by hand:** create `api.hadithbot.app` and `play.hadithbot.app` in Porkbun DNS; open ports 80/443 on the Oracle VM and install Caddy; create the Vercel project; in the Discord developer portal, turn on Activities, add one URL mapping and the `https://127.0.0.1` redirect, and copy the client secret; create the two Supabase tables (SQL below). Testing inside Discord is a manual click-through, and that's your call.

**Must happen before you switch on Activities:** the bot's `tree.sync()` will start failing at startup once the app has an Entry Point command (Phase 0). Ship that fix first.

**Open decisions (my recommendation in bold):**
1. On for every channel, or opt-in? **On by default, with `/bismillah setup name_match:False` to turn it off, announced in an update message.**
2. Post a separate "X just played" message for every run like MugUp does? **No. Edit the card only; per-run posts would spam announcement-style MSA channels.**
3. "2 sets in one exercise": I read it as names (set 1) + surahs (set 2) in the same daily match. **Do names-only first, add surahs once v1 has run for a couple of weeks.** Tell me if you meant something else.
4. Trust the score the game sends, or recompute it? **Recompute on the server from the list of guesses.** It's about 30 lines and keeps the board honest.

---

## Context

MugUp (`~/Desktop/projects/memoniq`) has a Discord Activity with a daily challenge whose
message doubles as a live leaderboard. HadithBot already posts a daily name of Allah and
hadith to every configured channel at 6 PM Toronto time. This adds a short daily game that
reviews the names the channel has been sent, and introduces MugUp to the people playing it.

The screenshots the user shared are MugUp's **website** pair match (`PairMatchGamePlay.tsx`,
10 pairs per set, one mixed grid, Shuffle / Next Set / Skip Set). MugUp's Discord Activity
uses a different component (`PairMatchRound`, 5 pairs, two columns). We want the website look,
so we port `PairMatchGamePlay`, not the Activity's player.

### What's different from MugUp, and why it makes this simpler

| MugUp | HadithBot | Effect |
|---|---|---|
| Many decks; the Activity can't tell which button launched it, so the bot writes a `discord_launch_intents` row per click | One match per channel per day | No launch intents. The channel id from the SDK is enough to find the match. |
| Each server picks a timezone; an hourly cron posts end-of-day boards | Every channel is posted at 6 PM Toronto | A "day" runs from one broadcast to the next. The broadcast itself closes yesterday's card. |
| HTTP interactions endpoint (Next.js route) | discord.py over the gateway | Button handler is a `DynamicItem` calling `interaction.response.launch_activity()` (available in our discord.py 2.7.1, checked). |
| Accounts, linking, XP, review queues | None | No account linking, no `discord_links`, no rich presence in v1. |
| Score sent by the client | Guesses sent by the client | Server replays the guesses and computes the score. |

---

## Architecture

```
Discord client
  └─ iframe: https://<app_id>.discordsays.com/   (Discord's proxy)
        URL mapping "/" → play.hadithbot.app        (Vercel, static React build)
        play.hadithbot.app/api/* ── Vercel rewrite ──► https://api.hadithbot.app/*   (Caddy on the VM)
                                                       └─ bot's aiohttp server (server.py, same event loop as the bot)
                                                            ├─ Supabase: game_days, game_results
                                                            └─ discord.py: edit the card message
```

Why the API lives in the bot process rather than on Vercel:
- The card has to be rendered in two places: when a score comes in, and at 6 PM when the bot
  closes yesterday's card. Keeping both in Python means one renderer with one set of tests.
- The bot already holds the bot token and the Supabase key, and discord.py already handles
  Discord's rate limits for message edits.
- `server.py` already runs an aiohttp app inside the bot's event loop (and its docstring
  explains why that is robust against stalled connections).

Why the Vercel rewrite: Discord's proxy only allows requests to URL-mapped hosts. A single
mapping (`/` → `play.hadithbot.app`) plus a Vercel rewrite keeps every fetch relative and
same-origin, exactly how MugUp does it (no `/.proxy` prefixes, no `patchUrlMappings`).

The cost: the game's API is down whenever the bot is down. That's acceptable, the bot is the
product, and UptimeRobot already watches it.

---

## Phase 0: make command sync survive the Entry Point command (ship first)

Turning on Activities in the developer portal gives the app an **Entry Point command**
(type 4, "Launch"). Discord rejects a bulk command overwrite that leaves it out (error 50240,
"You cannot remove this app's Entry Point command in a bulk update operation"). `setup_hook`
calls `self.tree.sync()`, which does exactly that bulk overwrite, so the bot would fail to
start after the portal change.

1. Check whether discord.py 2.7.1 handles this already (read `CommandTree.sync` and the
   `bulk_upsert_global_commands` payload; search the changelog for "entry point").
2. If not: replace the `tree.sync()` call with a small `sync_commands(bot)` in a new module
   that fetches the current global commands (`bot.http.get_global_commands`), keeps any with
   `type == 4`, and calls `bot.http.bulk_upsert_global_commands` with the tree's payload plus
   that entry. MugUp's `scripts/discord/register-commands.mjs` does the same thing in JS.
3. Unit test the merge function (pure: existing commands + tree payload → PUT body).

Entry Point handler: set it to **"Discord launches the Activity"** (handler 2) in the portal.
Discord then posts its own invitation card and the bot needs no handler for it. Launches
from the App Launcher land on the practice screen (screen 8 in the mockup) unless the
channel has a match today.

---

## Phase 1: data and the daily card (bot side, no Activity yet)

### Supabase tables

HadithBot has no migrations folder; tables are created in the dashboard. SQL to run:

```sql
create table game_days (
  channel_id   text not null,
  day_key      date not null,          -- broadcast date in America/Toronto
  guild_id     text,
  game         text not null default 'names_10',
  items        jsonb not null,         -- frozen pairs, see below
  message_id   text,                   -- the card, set after it's posted
  posted_at    timestamptz not null default now(),
  closed_at    timestamptz,            -- set when the next broadcast finalises it
  primary key (channel_id, day_key)
);

create table game_results (
  id              bigint generated always as identity primary key,
  channel_id      text not null,
  day_key         date not null,
  guild_id        text,
  discord_user_id text not null,
  display_name    text not null,
  score           int  not null check (score >= 0),
  total           int  not null check (total > 0 and score <= total),
  item_results    jsonb not null,      -- [true|false|null] per pair, in name order
  guesses         jsonb not null,      -- the raw guess log, for audits
  duration_ms     int  check (duration_ms > 0 and duration_ms <= 21600000),
  created_at      timestamptz not null default now(),
  unique (channel_id, day_key, discord_user_id),
  foreign key (channel_id, day_key) references game_days on delete cascade
);
create index game_results_board on game_results (channel_id, day_key, score desc, duration_ms asc);

alter table discord_channel_state add column name_match_enabled boolean not null default true;
```

`items` shape (frozen at broadcast so later edits to `99names.json` can't change a day's match):

```json
{"sets": [{"kind": "names", "pairs": [
  {"id": 49, "left": "49. Al-Baa'ith", "left_ar": "الْبَاعِثُ", "right": "The Resurrector"}, ...
]}]}
```

`sets` is a list from day one so v2 (surahs) only appends a second entry.

### New module `name_match.py` (pure, no `db` import, like `views.py`)

- `pick_names(last_sent: int, total: int = 99, count: int = 10) -> list[int]`: the 10
  consecutive numbers ending at the last name sent today, wrapping 99 → 1; numbers 1 to 10
  when fewer than 10 have been sent. Note the channel's `last_name_no` is the *next* name to
  send after the broadcast advances it, so compute from the names actually sent this batch.
- `build_items(names, numbers) -> dict` → the `items` jsonb.
- `score_guesses(pairs, guesses) -> (score, item_results)`: replay. A guess is
  `[name_id, meaning_id]`. Same id: matched; clean if neither card was ever in a wrong pair.
  Different ids: both pairs become "missed" (MugUp's rule from `PairMatchGamePlay` L154-222).
  Reject guesses that reuse an already-matched card or reference ids not in the set.
  Unmatched pairs at the end are `null` (⬜).
- `rank(results)`: score desc, then `duration_ms` asc (untimed last), then `created_at` asc,
  then user id. Ported from MugUp `lib/discord/ranking.ts` L54-84.
- `squares(item_results) -> str`: 🟩 / 🟥 / ⬜, one row per set, 10 per row.
- `format_duration(ms)`: `48s`, `1m 05s`, `1h 03m` (port of MugUp `score-grid.ts`).
- `played_line(names)`: `Nobody has played yet.` / `**A** played` / `**A** and **B** played` /
  `**A**, **B** and 2 others played`.
- `streak_line(day_keys, today)`: `This server has played N days in a row 🔥`, only when N ≥ 2.
  (Counts days on which at least one person in the channel played.)
- `card_embed(day, results, final: bool) -> discord.Embed` and `card_view(final) -> View`.
  Live: no medals, top 10, `_and 4 other players_` beyond that. Final: 🥇🥈🥉 then `**4.**`,
  title `Final results: name match for Wed 21 Oct`, no Play button.
- Everything a user typed (display names) goes through `discord.utils.escape_markdown`.
- **No em dashes in any rendered string.** MugUp's lines put an em dash before the mention; ours use ` · `.

Exact copy is in the mockup; the strings to use:

| Where | Text |
|---|---|
| Title (live) | `Today's name match: 10 names of Allah` |
| Description, first paragraph | `Match today's name, {translit}, and the 9 names before it to their meanings. Everyone in this server gets the same 10 and one try each. Scores appear in this message until tomorrow's hadith is posted.` (when 2 or 3 names were sent today: `today's names, A and B, and the 8 names before them`) |
| Empty | `Nobody has played yet.` |
| Player block | `**9/10** · 1m 05s · <@id>` newline squares |
| Footer (live) | `🟩 right on the first try · 🟥 took more than one try · ⬜ stopped before matching it` newline `Names 49 to 58 · The matching game comes from MugUp, mugup.app` |
| Final title | `Final results: name match for {Ddd D Mon}` |
| Final first line | `6 people played. Today's match is in the newest message from HadithBot.` / `Nobody played this one.` |
| Buttons | primary `Play today's match` (custom_id `play_name_match`), link `All 99 names on MugUp` → `https://mugup.app/decks/101` |

Embed colour: HadithBot's site accent `#c8883a`.

### Bot changes

- `views.py`: `PlayNameMatchButton` (`DynamicItem`, template `play_name_match`), callback
  `await interaction.response.launch_activity()`. Register it in `setup_hook` next to
  `ExplainHadithButton`. If launching fails (Discord returns an error when the member lacks
  the **Use Activities** permission in that channel), reply ephemerally:
  `You need the "Use Activities" permission in this channel to play. A server admin can turn it on in the channel's settings.`
  Check what discord.py raises here before relying on it.
- `bot.py` `run_daily_broadcast`, per channel, after the hadiths are sent and only if
  `name_match_enabled`:
  1. Close yesterday's card: load the latest open `game_days` row for the channel, fetch its
     results, `edit` the message with `card_embed(final=True)`, set `closed_at`. Wrap in its own
     try so a deleted message never blocks today's post.
  2. Insert today's `game_days` row (upsert on the PK so `/bismillah send-now` on the same
     day reuses it rather than failing), post the card, store `message_id`.
- `/bismillah setup`: add `name_match: Optional[bool]`; `/bismillah status` shows it.
- `db.py`: `create_game_day`, `set_game_day_message`, `get_open_game_day(channel_id)`,
  `close_game_day`, `get_game_results(channel_id, day_key)`, `insert_game_result` (returns the
  existing row on a unique violation), `get_played_day_keys(channel_id, limit=60)`.

Ship Phase 1 with the Play button hidden (feature flag env `NAME_MATCH_LIVE=0`) or skip the
button until Phase 3 is deployed, so nobody presses a button that opens nothing.

---

## Phase 2: the API in `server.py`

New module `game_api.py`, mounted on the existing aiohttp app under `/` paths (the Vercel
rewrite strips `/api`). Every route except `/token` requires `Authorization: Bearer <token>`.

| Route | Does |
|---|---|
| `POST /token` `{code, guildId, channelId}` | Exchanges the code at `https://discord.com/api/v10/oauth2/token` (client id + secret, **no** `redirect_uri`), reads `GET /users/@me`, mints a session token. Returns `{token, player: {id, displayName}}`. Display name is `global_name`, else `username`. |
| `GET /today` | The channel's open `game_days` row if there is one: `{mode: "daily", dayKey, sets, myResult?, board}`. Otherwise `{mode: "practice", sets: <10 random names>}`. DMs (`guildId` null) are always practice. |
| `POST /result` `{dayKey, guesses, stopped, durationMs}` | Checks `dayKey` is the channel's open day (so a game started at 5:59 PM and finished at 6:01 PM still counts for the day it started, as long as it's the one just closed within, say, 10 minutes). Replays guesses, inserts the result, schedules a card edit, returns `{result, board}`. A second submission returns the first result with `recorded: false`. |

Session token: port MugUp `lib/discord/signed-payload.ts` + `activity-token.ts` to Python
(`hmac` + `base64.urlsafe_b64encode`). Payload `{uid, name, guild_id, channel_id, exp}`,
2-hour expiry, secret `ACTIVITY_TOKEN_SECRET` (32+ chars). Guild and channel are sealed
into the token at sign-in and never read from later request bodies.

Card edits: debounce per message. When a result lands, schedule an edit 2 seconds out unless
one is already pending; the edit re-renders from all of the day's rows (MugUp's approach, so
a failed edit fixes itself on the next one). This keeps a burst of finishers under Discord's
per-channel edit limit. Use `channel.get_partial_message(message_id).edit(...)`.

Limits: per-user rate limit on `/token` and `/result` (every request reaches us from Vercel's
IPs, so limit by Discord user id from the token, and by code for `/token`). Sanity-check
`durationMs`: at least 3 seconds per pair matched, at most 6 hours.

New env vars on the VM: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `ACTIVITY_TOKEN_SECRET`.
Add to `.env.example` and `docker-compose.yml`.

---

## Phase 3: the game screen (`activity/`)

Vite + React + TypeScript + Tailwind 3. Its own `package.json`; nothing in the bot depends on it.

Port from MugUp:
- `components/discord/use-activity-session.ts`: `new DiscordSDK(clientId)`, `ready()` with
  a 5 s timeout ("Open this from Discord" when it times out), `authorize` with scope
  `['identify']` and `prompt: 'none'`, `POST /api/token`, `authenticate`. Drop
  `rpc.activities.write` and presence for v1.
- `components/games/pairMatch/PairMatchGamePlay.tsx`: card model, pick logic, the 1-second
  wrong-pair display, Shuffle, the progress bar. Strip deck loading, sessions API, XP,
  sounds, keyboard-shortcut help, Previous/Next/Skip Set.
- `components/games/GameTimer.tsx`.
- Tailwind palette from the screenshots: sky for names, amber for meanings, emerald for
  matched. Wrong pairs show rose for the second (the website shows them as "selected", which
  is harder to read). Copy `button`, `progress`, `alert-dialog` from MugUp's shadcn set, or
  plain elements; no Radix dropdowns needed.

Screens (all in the mockup, with final wording):
1. Start: rules on screen, `Start the timer and play`. The timer starts on this press.
2. Playing: `3 of 10 matched`, `1 wrong guess`, the timer, `Shuffle the cards`,
   `Stop and post my score`. Phones (under 640px wide): names column left, meanings right,
   each shuffled, instead of the mixed grid.
3. Stop confirm: `Stop now and post 2 out of 10?` / `Keep playing` / `Stop and post 2/10`.
4. Result: `9 of 10 on the first try`, time, the squares, which names were missed, the board,
   the MugUp card with `Open the 99 names on MugUp` (via `sdk.commands.openExternalLink`).
5. Already played today: the same result screen, loaded from `myResult`.
6. Practice: `Practice: match 10 names of Allah`, says it isn't scored.

The client records `guesses` as `[nameId, meaningId]` in order and posts them with
`durationMs` when the last pair is matched or the player stops. If the page is closed mid-game,
nothing is posted and they can still play (MugUp's `sendBeacon` partial save isn't worth it
for a one-try game; a closed tab is closer to "didn't play" than "scored 3").

Constraints from Discord's proxy (MugUp `docs/private/discord-companion.md`):
- No third-party scripts, fonts or images: self-host the Arabic font (e.g. Noto Naskh
  Arabic woff2) and anything else.
- No cookies. Everything goes through the bearer token.
- `vercel.json` in `activity/`: rewrite `/api/:path*` → `https://api.hadithbot.app/:path*`;
  header `Content-Security-Policy: frame-ancestors https://*.discordsays.com https://discord.com`,
  and no `X-Frame-Options`.
- Discord opens the root with `?frame_id=&instance_id=...`; a single-page app at `/` handles it
  without MugUp's rewrite.

Credit line at the bottom of the game: `Matching game by MugUp` (not a link mid-game, so
nobody leaves by accident).

---

## Phase 4 (v2): a second set, surahs

- `data/114surahs.json`: number, transliteration, Arabic, English meaning. Export from MugUp
  deck 102 ("Surahs of the Quran: Names & Meanings") so the meanings match what MugUp shows,
  and review them.
- Which 10 surahs: no per-channel position exists for surahs, so walk a fixed order (1 to 114
  in blocks of 10, per channel, stored as `last_surah_no` on `discord_channel_state`).
- `items.sets` gets a second entry; the game clears set 1, then loads set 2 with no button
  press; header `Set 2 of 2: match each surah to its meaning`. Score out of 20, one row of
  squares per set, footer `Row 1: names of Allah · Row 2: surahs`.
- Title becomes `Today's match: 10 names of Allah and 10 surahs`.
- MugUp link button switches to whichever deck fits, or stays on the 99 names.

---

## Manual setup (you)

1. **Discord developer portal** (HadithBot application):
   - Only after Phase 0 is deployed: Activities → enable. Set the Entry Point command handler
     to "Discord Launches Activity".
   - URL Mappings: one row, `/` → `play.hadithbot.app`.
   - OAuth2 → Redirects: add `https://127.0.0.1` (needed for the code exchange).
   - Copy Client ID and Client Secret into the VM's `.env`.
   - A second "HadithBot Dev" application is worth having for testing the Activity, since
     URL mappings are one set per application. Do you already have a dev bot?
2. **Porkbun DNS**: `A api.hadithbot.app → <VM public IP>`; `CNAME play.hadithbot.app → cname.vercel-dns.com`.
3. **Oracle VM**: ingress rules for TCP 80 and 443, the matching `iptables` lines (as
   DEPLOY.md does for 8080), install Caddy with `api.hadithbot.app { reverse_proxy localhost:8080 }`.
   Add the steps to DEPLOY.md as part of Phase 2.
4. **Vercel**: new project from this repo, root directory `activity/`, domain `play.hadithbot.app`.
5. **Supabase**: run the SQL above.
6. **Announce it**: an `updates/YYYY-MM-DD.md` message saying what the new last message is,
   that it's one try a day, and how to turn it off (`/bismillah setup name_match:False`).

---

## Testing

Static, per your usual loop (`make test`, `make lint`):
- `name_match.py`: `pick_names` at 1, 5, 10, 58, 99 and wrapping; `score_guesses` (clean run,
  one miss dirties both pairs, reused card rejected, unknown id rejected, stopped early gives
  ⬜); `rank` tie order; every rendered string compared exactly (live, empty, >10 players,
  final with medals); no em dash (U+2014) in any output.
- Token sign/verify: round trip, tampered payload, expired, wrong secret.
- Command sync merge (Phase 0).
- `game_api.py` routes with aiohttp's test client and a fake db (same style as
  `tests/test_health_server.py`).
- `activity/`: vitest for the pick logic and guess log (port MugUp's `pair-match-scoring.test.ts`
  cases that still apply), `tsc --noEmit`, eslint.

Inside Discord there's no automated test; a click-through on the dev app is the only check.
That's yours to decide when to do.

---

## Files touched

New: `name_match.py`, `game_api.py`, `command_sync.py`, `tests/test_name_match.py`,
`tests/test_game_api.py`, `tests/test_command_sync.py`, `activity/` (whole app).
Changed: `bot.py` (setup_hook sync, broadcast, setup/status options), `views.py`
(`PlayNameMatchButton`), `db.py`, `server.py` (mount routes), `.env.example`,
`docker-compose.yml`, `DEPLOY.md`, `README.md`.
