# App Directory listing

Everything needed for HadithBot's Discord App Directory page, in the order the
Developer Portal asks for it. Paste from here rather than rewriting each time —
the copy is deliberately consistent with the site and `OUTREACH.md`, so a person
who reads the listing and then the site doesn't get two different pitches.

Portal path: **Developer Portal → HadithBot → App Directory**.

## Eligibility — read first

Discoverability does not unlock on request. Discord gates it, and the gate that
actually binds here is the server count:

| Requirement | Where it stands |
| --- | --- |
| **75+ servers** | The binding constraint. `make health` reports the live count. Until it's met, the Discoverability section stays locked and nothing below can be submitted. |
| Verified app | Requires the 75-server threshold first; verification and discoverability are applied for together. |
| Terms of Service URL | Have it — https://hadithbot.app/terms |
| Privacy Policy URL | Have it — https://hadithbot.app/privacy |
| Description, icon, categories | Below. |
| Safe-for-work content | Fine. |
| Slash commands registered | Twelve, under `/bismillah`. |

So the sequence is: **grow to 75 servers → apply for verification + discoverability
→ paste this listing**. The assets and copy here are written now because they're
the same material `OUTREACH.md` needs today, and because the listing should not
be drafted in a hurry on the day the gate opens.

## Assets

Generated into `assets/appdir/` from the existing site art. Deliberately outside
`docs/` — that directory is the deployed Vercel root, and these are upload
material for the portal, not pages of the site.

| Asset | File | Size | Notes |
| --- | --- | --- | --- |
| App icon | `icon-1024.png` | 1024×1024 | Upscaled from the 144px `akh.png`. **Soft at full size — see below.** |
| App icon (fallback) | `icon-512.png` | 512×512 | Same source, less visible upscaling. |
| Carousel 1 | `carousel-1-daily-1920.png` | 1920×1080 | The real daily message: two names plus a hadith with the Sunnah.com link. |

**The icon needs attention before submission.** Both sizes are upscaled from a
144×144 original, which is under Discord's 512×512 minimum, so they will look
soft next to competing listings. The fix is to re-export the artwork from
whatever produced `akh.png` at 1024×1024 native and drop it in over
`icon-1024.png`. If that source is gone, this is the one asset worth having
redrawn — it is the single image that appears everywhere in the directory.

**Two more carousel images are still needed.** Discord shows up to five and the
listing looks thin with one. Both should be captured at 1920×1080 from a real
server, not mocked:

1. **`/bismillah setup` in use** — run it in a test channel and capture the
   confirmation reply. This is the "it takes one command" claim, shown rather
   than asserted.
2. **`/bismillah random` or a name lookup** — capture the ephemeral reply, to
   show the bot answers on demand and isn't only a scheduled poster.

Capture on Discord's dark theme at 1600px+ width, then pad to 16:9 the same way:

```
sips -s format png -c <height> <width_for_16:9> --padColor 1E1F22 shot.png --out out.png
sips -s format png -z 1080 1920 --padColor 1E1F22 out.png --out final.png
```

`1E1F22` is Discord's dark chrome, so the letterboxing reads as part of the
screenshot instead of a border.

## Listing copy

### Name

```
HadithBot
```

### Short description

Shown on directory cards. Keep under ~80 characters.

```
A daily hadith and one of Allah's 99 names, posted to your server each evening.
```

### Long description

```
HadithBot posts one message a day into a channel you choose: a hadith from the
collections with a link straight to its source on Sunnah.com, and one of the 99
names of Allah with its meaning and a short note on when to call upon it.

Most community servers go quiet between events. This gives the server a small,
steady reason to exist in between — a reminder nobody has to remember to post.

**Setup takes one command.** Someone with Manage Server runs
`/bismillah setup #channel` and that's the whole thing. Every channel keeps its
own place in the collections, so a server that adds a second channel later
doesn't restart the first one.

**Members can ask any time.** `/bismillah random` for a hadith,
`/bismillah random_name` for one of the names, or look up a specific one by book
and chapter. These replies are private to whoever asked, so nobody floods the
channel.

**It can't read your messages.** HadithBot runs without Discord's Message
Content and Server Members intents — Discord does not send it the text of your
messages, and it has no list of your members. All it stores is which channel to
post in and which hadith it left off at.

Free, open source, no ads, no tracking.

Source: https://github.com/SaiyedRushan/HadithBot
Setup guide: https://hadithbot.app/send-daily-hadith-discord
```

### Categories

Discord allows two. In order of fit:

1. **Social** — closest to what it does; a scheduled community reminder.
2. **Utilities** — accurate fallback; it is a scheduled poster.

There is no religion or faith category, which is worth knowing going in: nobody
browsing the directory will find this by topic. Realistically the directory will
never be the main channel for an MSA-focused bot — the person-to-person route in
`OUTREACH.md` is. Treat the listing as something that makes the bot look
legitimate when someone already searching by name finds it, not as a growth
channel in its own right.

### Tags

Five maximum. These are the actual search surface, so they matter more than the
categories:

```
hadith
islam
daily
reminder
muslim
```

### Install link

Already live and used throughout `OUTREACH.md`:

```
https://discord.com/oauth2/authorize?client_id=1285370394282295359&permissions=3072&scope=bot%20applications.commands
```

`permissions=3072` is Send Messages + Read Message History — the minimum the bot
needs. Do not widen it for the listing. A small permission ask is a genuine
advantage over other bots on the same page and it is the thing an admin looks at
hardest.

### Supporting links

| Field | URL |
| --- | --- |
| Website | https://hadithbot.app |
| Terms of Service | https://hadithbot.app/terms |
| Privacy Policy | https://hadithbot.app/privacy |
| Support server | **Not set up — see below.** |

Discord asks for a support server or contact URL. There isn't one right now, and
the GitHub issues page is the honest substitute:

```
https://github.com/SaiyedRushan/HadithBot/issues
```

A real support server is worth considering before submitting — an admin
evaluating a bot often checks whether anyone is home. But it is a commitment to
answer, so an unattended server is worse than a link to issues.
