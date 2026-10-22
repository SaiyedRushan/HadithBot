# HadithBot name match (Discord Activity)

The game that opens when someone presses **Play today's match** under HadithBot's daily name match card. It shows 10 names of Allah and their 10 meanings in one shuffled grid of 20 cards, and the player matches each name to its meaning. It's a port of the pair match game on MugUp's website.

It's a static Vite + React app. Everything it knows comes from the bot's API: `POST /api/token`, `GET /api/today` and `POST /api/result`, all relative URLs with a bearer token. The bot recomputes the score from the list of guesses, so the rules in `src/game.ts` have to agree with `score_guesses` in the bot.

## Files

- `src/game.ts`: the game rules as pure functions (cards, picks, the guess log, scoring, squares, time formats). Tested in `src/game.test.ts`.
- `src/discord.ts`: the Discord sign-in (`ready`, `authorize`, then `POST /api/token`).
- `src/api.ts`: the API types and calls. Errors come back as `{"error": "..."}` and that sentence is shown to the player.
- `src/App.tsx`, `src/Play.tsx`, `src/Result.tsx`: the screens. Wording follows `plans/name-match-mockup.html`.

## Checks

```bash
npm install
npm test            # vitest
npm run typecheck   # tsc --noEmit
```

Outside Discord the app only shows "Open this from the Play button under HadithBot's daily name match in Discord." Testing the full game means launching it from the dev app in Discord.

## Deploy (Vercel)

- New Vercel project from this repo with **Root Directory** set to `activity/`. Vercel picks up Vite on its own (build `npm run build`, output `dist`).
- Environment variable: `VITE_DISCORD_CLIENT_ID`, the HadithBot application's client ID. It's baked in at build time, so redeploy after changing it. See `.env.example`.
- Domain: `play.hadithbot.app`. In the Discord developer portal, the Activity's URL mapping is `/` to `play.hadithbot.app`.
- `vercel.json` rewrites `/api/*` to `https://api.hadithbot.app/api/*`, sends every other path to `index.html`, and sets `Content-Security-Policy: frame-ancestors` so Discord can show the page in its frame. Don't add `X-Frame-Options`.
- Discord's proxy blocks fonts, scripts and images from other hosts, so everything is bundled, including the Arabic font (`@fontsource/noto-naskh-arabic`).
