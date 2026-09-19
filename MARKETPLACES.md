# Bot marketplace listings

Copy-paste material for listing HadithBot on third-party Discord bot
directories. This is separate from `APP_DIRECTORY.md`, which covers Discord's
own App Directory. That one is gated at 75 servers and can't be submitted yet.
These directories have no such gate, so they're what's actually actionable now.

The point of them is backlinks and name recall, not installs. A page on a
high-authority domain is what makes "hadithbot discord" resolve to something
other than the GitHub repo, and it's the kind of page an LLM will cite when
someone asks it for an Islamic Discord bot. Treat installs as a bonus.
`OUTREACH.md` is still the real growth channel.

## Facts you'll paste over and over

| Field | Value |
| --- | --- |
| Bot ID / Client ID | `1285370394282295359` |
| Library | discord.py |
| Prefix | slash-only (no message-prefix commands) |
| Invite URL | `https://discord.com/oauth2/authorize?client_id=1285370394282295359&permissions=3072&scope=bot%20applications.commands` |
| Website | `https://hadithbot.app` |
| Repo | `https://github.com/SaiyedRushan/HadithBot` |
| Privacy | `https://hadithbot.app/privacy` |
| Terms | `https://hadithbot.app/terms` |
| Support | No Discord support server. Use `https://github.com/SaiyedRushan/HadithBot/issues` where a plain URL is accepted, and leave the field blank where it demands an invite code. |

Every one of these sites requires **Log in with Discord** before you can submit.
Use the account that owns the application.

---

## 1. discord.bots.gg

Field by field, in the order the "Add a Bot" form lists them.

**☑ This bot only supports slash commands.** Check it. `bot.py:47` sets
`command_prefix="!"` but registers zero prefix commands. Everything is an
app command under the `/bismillah` group.

### Bot ID *

```
1285370394282295359
```

### Prefix * (max 100)

Required even for slash-only bots, so:

```
/
```

### Help Command * (max 200)

There is no `/bismillah help` command. Don't invent one. An admin who types a
command that doesn't exist and gets nothing back is worse off than one who got
a vague answer. The honest field:

```
/bismillah
```

Or the fuller version, still inside 200 characters:

```
/bismillah, then pick from the list Discord shows as you type. /bismillah setup #channel starts the daily message.
```

> If you'd rather this be a real command, adding `/bismillah help` is a small
> change and it would improve every listing that asks for one. Not required
> today.

### Overview * (max 200)

```
A daily hadith and one of Allah's 99 names, posted to your server each evening.
```

### Bot Library *

```
discord.py
```

### Co-owners

Leave empty.

### Invite URL * (max 2000)

```
https://discord.com/oauth2/authorize?client_id=1285370394282295359&permissions=3072&scope=bot%20applications.commands
```

Do not widen `permissions=3072`, which is Send Messages plus Read Message
History. The small permission ask is a real advantage on a page full of bots
requesting Administrator, and it's the thing a server admin looks at hardest.

### Website (max 2000)

```
https://hadithbot.app
```

### Support Server Invite (max 48)

Leave blank. The field wants a `discord.gg` invite and there isn't one. The
GitHub issues URL doesn't belong here and probably won't validate.

### Open Source Repository (max 2000)

```
https://github.com/SaiyedRushan/HadithBot
```

### ☐ This bot is only Turkish

Leave unchecked.

### Description * (max 10000, Markdown, two newlines for a line break)

Paste exactly this. The blank lines matter, because the form's Markdown needs
two newlines to break a line.

```
HadithBot posts one message a day into a channel you choose: a hadith from the collections with a link straight to its source on Sunnah.com, and one of the 99 names of Allah with its meaning and a short note on when to call upon it.

Most community servers go quiet between events. This gives the server a small, steady reason to exist in between, a reminder nobody has to remember to post.

## Setup takes one command

Someone with Manage Server runs `/bismillah setup #channel` and that's the whole thing. Every channel keeps its own place in the collections, so a server that adds a second channel later doesn't restart the first one.

## Members can ask any time

`/bismillah random` for a hadith, `/bismillah random_name` for one of the names, or look up a specific one by book and chapter. These replies are private to whoever asked, so nobody floods the channel.

## It can't read your messages

HadithBot runs without Discord's Message Content and Server Members intents. Discord does not send it the text of your messages, and it has no list of your members. All it stores is which channel to post in and which hadith it left off at.

## Commands

`/bismillah setup` starts daily messages in a channel
`/bismillah stop` stops them
`/bismillah status` shows where a channel is up to
`/bismillah random` sends a random hadith, privately
`/bismillah specific` looks up a hadith by book and chapter
`/bismillah random_name` sends a random one of the 99 names
`/bismillah specific_name` looks up one of the names by number
`/bismillah specific_names` sends three of the names, starting at a number
`/bismillah books` lists the collections and their ids
`/bismillah chapters` lists the chapters in a collection
`/bismillah send-now` posts today's message immediately
`/bismillah diagnose` explains why a channel isn't receiving posts
`/bismillah flags` shows hadiths members have reported
`/bismillah flag-reply` replies to whoever reported one

Free, open source, no ads, no tracking.

Website: https://hadithbot.app
Setup guide: https://hadithbot.app/send-daily-hadith-discord
Source: https://github.com/SaiyedRushan/HadithBot
Privacy policy: https://hadithbot.app/privacy
```

Then hit **Submit**. Most directories queue new bots for a human to review, so
expect a wait of hours to days, and expect the bot to need to be online when a
reviewer looks at it.

---

## 2. top.gg

The one worth doing carefully. It is by far the highest-traffic and
highest-authority of these, and it's the page most likely to end up as the top
non-GitHub result for the bot's name.

Start at `https://top.gg/bot/new`. It will bounce you to Discord login first.

The fields differ from bots.gg but the material is the same:

- Short description: `A daily hadith and one of Allah's 99 names, posted to your server each evening.` (79 characters)
- Long description: the Markdown block above
- Prefix: `/`, and tick the slash-commands option if it's offered
- Tags: `hadith`, `islam`, `daily`, `reminder`, `muslim`. These are the real
  search surface. The categories aren't.
- Categories: Social first, then Utilities. There is no religion category.
- Links: website, GitHub, privacy and terms as in the table above

### What the competition looks like (checked 19 September 2026)

Searching top.gg for `hadith` returns IslamBot, AhadithsRadio, Fajr, NAVA CHAT
and a second IslamBot. Every one of them showed **0 votes**. Searching `quran`
returns a much stronger field, with QuranBot at 3.48K servers and VetroniqBot
Quran at 17.9K.

So `quran` is contested and `hadith` is not. Nobody is defending that keyword.
Lead every listing with "hadith" rather than with "Islamic": the tag, the name,
the first four words of the description. That's the cheapest ranking you will
get anywhere.

Vote counts drive top.gg's own ranking, so once the listing is live the vote
link is a reasonable thing to put in the York MSA server. Once. Repeatedly
asking for votes is how a small bot burns the goodwill that got it installed.

---

## 3. discordbotlist.com

The third of the three I confirmed alive and accepting submissions. Log in with
Discord, then add the bot from the dashboard. Same material again. It asks for a
longer description and supports Markdown, so paste the same block.

---

## 4. The tail

Worth doing after the first three are live, in one sitting, since each is the
same paste and takes a few minutes. Check each one is still alive before
spending time on it. This corner of the web churns and several well-known lists
have gone dark over the years. I did not verify these the way I verified the
three above.

- `discords.com/bots`, high authority, formerly Bots For Discord
- `discadia.com`, mostly servers but it lists bots
- `botlist.me`, `disforge.com`, `infinitybots.gg`, `wumpus.store`,
  `discordlist.gg`, all smaller, all still real backlinks

If a site makes a support server invite a required field, skip it rather than
spinning up a server you won't watch. A support server nobody answers is worse
for an admin evaluating the bot than no support server at all.

---

## Beyond bot directories

Directories are backlinks. If the goal is that an LLM recommends HadithBot when
someone asks for a good Islamic Discord bot, these matter at least as much, and
they're entirely in your control.

**GitHub topics.** The repo should carry `discord-bot`, `discord-py`, `hadith`,
`islam`, `sunnah` and `python`. GitHub topic pages get crawled hard and this
takes thirty seconds in the repo settings.

**Structured data on more than the homepage.** `docs/index.html` already has
`SoftwareApplication` and `FAQPage` JSON-LD. None of the other pages have any.
`send-daily-hadith-discord.html` is the one that answers a question people
actually type, so it deserves its own `HowTo` or `FAQPage` block. This is the
highest-value item on the page and it beats the entire tail of small bot lists.

**AlternativeTo and Product Hunt.** Both rank well and both get quoted back by
AI search. Product Hunt is a one-shot launch, so save it until the icon is
redrawn. `APP_DIRECTORY.md` explains why: the current one is upscaled from
144px and looks soft next to everything around it.

**Awesome-lists.** A PR adding HadithBot to `awesome-discord`, or to an
`awesome-islam` list, is a citation that sticks around.

**Reddit, carefully.** r/discordapp and r/Discord_Bots both allow
self-promotion in the right threads. r/islam is stricter. Read the sidebar
first, because a removed post is worse than no post.
