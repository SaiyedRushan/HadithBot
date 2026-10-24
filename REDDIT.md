# Reddit post

Copy-paste drafts for introducing HadithBot on Reddit. Written in the first
person, as the person who made it and uses it. That's the only voice that works
on Reddit, and here it happens to be true.

Same rules as `OUTREACH.md`: don't overstate it, don't post it anywhere the
subreddit doesn't allow self-promotion, and answer honestly in the comments.

The post deliberately doesn't explain how to install it. Anyone who wants it
will click the site, and the site does that job better than a paragraph can.
Leaving setup instructions out is also what keeps the post from reading like an
ad.

---

## Before you post

1. **Check the subreddit's self-promotion rule.** r/islam, r/MuslimCorner,
   r/MuslimLounge and r/Muslim all draw the line differently, and some want mod
   approval first. A removed post wastes the effort and makes the next one
   harder. Message the mods if the rule isn't clear.
2. **Post the screenshot as an image, not a link.** Reddit buries link posts. Use
   an image post, or a text post with the image uploaded into it, and put the
   write-up in the body.
3. **Post from your own account, not a fresh one.** A day-old account posting a
   link reads as spam whatever the post says.

**Screenshot to attach:** `assets/appdir/carousel-1-daily-1920.png`. It's a real
daily message from a live server, showing two of Allah's names with their
meanings and a hadith with the Sunnah.com button. Already 1920x1080 and cropped
for posting.

For a second image, `docs/img/discord-example.png` is the same message at the
size the website uses.

---

## Main draft, for r/islam, r/MuslimCorner, r/Muslim

**Title options.** The first is the most honest and the least salesy:

```
I made a free Discord bot that posts a daily hadith and one of Allah's 99 names. My MSA has been using it for a year.
```

```
A free, open-source Discord bot for a daily hadith and one of Allah's names. Built it for my MSA, sharing it in case it's useful.
```

```
My friends and I go through one hadith and one of Allah's names a day in our Discord. I turned it into a bot anyone can add.
```

**Body:**

> Assalamu alaikum everyone,
>
> I made a small Discord bot for my university's MSA a year ago, and it turned
> into something I use every day. Sharing it in case it's useful to anyone else.
>
> **What it does.** Every evening it posts one message into a channel you pick: a
> hadith with its book and chapter and a button that opens it on Sunnah.com, and
> one of Allah's 99 names with its meaning and a short line on when to call on it
> in your dua. You set it up once and it just turns up.
>
> **Why I made it.** Consistency beats intensity and I'm bad at consistency. I
> was never going to open a hadith collection every evening on my own. One short
> hadith arriving in a channel I'm already in, that I don't have to remember, is
> the thing that actually stuck.
>
> The names were the surprise. It goes through all 99 in order and loops back to
> the start. I didn't set out to memorise them, but seeing the same name come
> back around every few months, with its meaning, has done more than any list I
> tried to sit down and learn. Just repetition over a long time.
>
> **The details:**
>
> - Free, open source, no ads, nothing to sign up for.
> - **It can't read your messages.** It runs without Discord's Message Content
>   and Server Members intents, so Discord doesn't send it your messages and it
>   has no list of your members. All it stores is which channel to post in and
>   where that channel left off.
> - 17 collections, around 50,000 hadiths. Bukhari, Muslim, Nasa'i, Abu Dawud,
>   Tirmidhi, Ibn Majah, Riyad as-Salihin, Nawawi's 40 and more. Each channel
>   keeps its own place and works straight through.
> - You choose how many hadiths and names go out per day, 1 to 10 each, default
>   3. For the one-a-day thing I described, set both to 1.
> - Anyone can ask for one on the spot with a slash command, and that reply is
>   private to whoever asked, so nobody floods the channel.
> - Every message links to Sunnah.com and has a flag button to report anything
>   that looks wrong. I'd rather know.
>
> It's free and takes about a minute to set up: **https://hadithbot.app**
>
> Code is on GitHub if you'd rather read it first or host it yourself:
> https://github.com/SaiyedRushan/HadithBot
>
> I'm not a scholar and the bot isn't one either. It carries the text and points
> you at the source. If you spot a mistake, the flag button or a GitHub issue
> both reach me.
>
> Happy to answer anything in the comments. Jazakum Allahu khayran.

---

## Short version, for subreddits that want it brief, or for a comment reply

> Assalamu alaikum. I made a free Discord bot that posts a daily hadith and one
> of Allah's 99 names into a channel of your choice, each with its meaning and a
> link to the source on Sunnah.com.
>
> I built it for my university MSA and my friends use it too. One hadith a day,
> and the names loop around so you end up learning them just from seeing them
> come back.
>
> Open source, no ads, and it can't read your messages. It runs without the
> Message Content intent.
>
> https://hadithbot.app

---

## For r/discordapp, r/Discord_Bots, r/SideProject

Those subs care about the build, not the reminder. Lead with the one technical
choice that's actually interesting: no message content intent.

**Title:**

```
I built a Discord bot that posts a daily reading to a channel, deliberately without the Message Content intent
```

**Body:**

> I built a bot for my university's MSA Discord that posts one scheduled message
> a day: a hadith with a source link, plus one entry from a 99-item list it
> cycles through and loops.
>
> The constraint I set myself was that an admin who doesn't trust me at all
> should still be comfortable adding it. So it runs with no Message Content
> intent and no Server Members intent, and asks for exactly two permissions,
> Send Messages and Read Message History. It genuinely cannot read anything in
> the server. Everything is slash commands, and the only per-channel state is a
> channel id and a cursor into the collection.
>
> Stack is Python and discord.py, Supabase for the data (~50k rows of source text
> across 17 collections), a Flask health endpoint, deployed in Docker. On-demand
> command replies are ephemeral so a busy server doesn't get flooded.
>
> The part I got wrong twice: re-running the setup command used to reset a
> channel's reading position, because I treated blank optional args as "set to
> default" instead of "leave alone". Now a blank field keeps its current value,
> which is what anyone would expect.
>
> Source: https://github.com/SaiyedRushan/HadithBot
> Site: https://hadithbot.app

---

## Answers for the comments you'll get

**"How do I know it's not reading my messages?"**
> Fair question. Two things you can check without taking my word for it. The
> authorization screen shows exactly what it asks for, Send Messages and Read
> Message History and nothing else. And the intents are set in the source, in
> `bot.py`, where the `discord.Intents` are configured. If it were reading
> messages, Discord would make it declare that.

**"Who verified the hadiths?"**
> They come from the standard collections, and every message names its book and
> chapter with a button straight to Sunnah.com, so you can check any of them in
> one click. I'm not a scholar, and the bot doesn't grade authenticity or add
> commentary. There's a flag button on every message and I fix what gets
> reported.

**"Can it do Quran verses, prayer times, Arabic text?"**
> Not right now. It posts a hadith and the names, and I'd rather it do that one
> thing well than half-do five. Prayer times I built separately as a phone app,
> Hayya, listed on the site. Feature requests are welcome on GitHub.

**"Is this going to become paid, or get ads?"**
> No. It costs me a few dollars a month to run and it's open source. If I ever
> stopped running it, anyone could host it themselves from the same code.

**"Can I change the time? It's not evening for me."**
> Not yet, honestly. It goes out at 6:00 PM Toronto time for every server right
> now. Per-server timezones are the thing I most want to add next, and if a few
> people ask for it here I'll move it up.

---

## After it's posted

- Reply to everyone for the first few hours. That's what decides whether the post
  goes anywhere.
- If someone says they've added it to their MSA, point them at the listing form
  so their community can go on the site's wall:
  https://github.com/SaiyedRushan/HadithBot/issues/new?template=add-community.yml
- Don't cross-post the same text to five subreddits the same day. Reddit's spam
  filter notices, and so do people.
