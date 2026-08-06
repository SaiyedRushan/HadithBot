# Outreach kit

Copy-paste material for getting HadithBot into more MSA and community servers.
Nothing here is automated on purpose — a bot showing up because a person you
know vouched for it lands very differently from a cold DM at scale.

## Links you'll keep needing

| What | Where |
| --- | --- |
| Site | https://hadithbot.app |
| Add to Discord | https://discord.com/oauth2/authorize?client_id=1285370394282295359&permissions=3072&scope=bot%20applications.commands |
| Setup guide | https://hadithbot.app/send-daily-hadith-discord |
| 99 names | https://hadithbot.app/99-names-of-allah |
| Privacy | https://hadithbot.app/privacy |
| Source | https://github.com/SaiyedRushan/HadithBot |
| Ask to be listed on the site | https://github.com/SaiyedRushan/HadithBot/issues/new?template=add-community.yml |

## Who to ask

Only someone with **Manage Server** can add any bot to a Discord server — the
owner and admins always have it, moderators often don't. So the ask goes to the
exec team, not the general chat. In an MSA that usually means the president, the
VP internal, or whoever is listed as running the Discord.

One message, to the right person, in their exec group chat or DMs. If it doesn't
land, leave it — this is meant to be a gift, and chasing it turns it into a
pitch.

## Short DM — someone you know

> Assalamu alaikum! I built a small Discord bot that posts a hadith and one of
> Allah's names to a channel every evening — free, open source, no ads, no
> tracking, and it can't read any messages in the server. Takes about a minute
> to set up (`/bismillah setup #channel`).
>
> Thought it might be nice for the [NAME] server — a reminder that just turns
> up without anyone having to remember to post it. hadithbot.app if you want a
> look, no worries either way.

## Short DM — an MSA you don't know

> Assalamu alaikum wa rahmatullah,
>
> My name is [YOUR NAME], I'm with [YOUR MSA / school]. I made a free Discord
> bot called HadithBot that posts a daily hadith and one of the 99 names of
> Allah into whichever channel you point it at, with the meaning and a short
> reflection. It's already running in the York University MSA server.
>
> It's open source, collects nothing about your members, and can't read
> messages — Discord doesn't even send it the message content. Setup is one
> command and takes a minute: hadithbot.app
>
> If it'd be useful for [THEIR MSA], happy to help set it up. If not, no
> problem at all — jazakum Allahu khayran either way.

## Longer version — email or an exec meeting

> Assalamu alaikum wa rahmatullahi wa barakatuh,
>
> I wanted to share something with the [MSA NAME] team that might be useful for
> your Discord.
>
> **What it is.** HadithBot posts one message a day into a channel you choose:
> a hadith from the collections with a link straight to its source on
> Sunnah.com, and one of the 99 names of Allah with its meaning and a short note
> on when to call on it. It goes out at a set time each evening. Members can
> also pull a hadith on demand with a slash command.
>
> **Why it might help.** Most MSA servers go quiet between events. This gives
> the server a small, steady reason to exist in between — and a reminder nobody
> has to remember to post.
>
> **What it costs.** Nothing. It's free and open source, and I run it myself.
>
> **What it can see.** Almost nothing, by design. It runs without Discord's
> Message Content and Server Members intents, so it can't read your messages and
> has no list of your members. All it stores is which channel to post in and
> which hadith it left off at. The privacy policy is at
> hadithbot.app/privacy and the code is public.
>
> **Setup.** Someone with Manage Server adds it from hadithbot.app, then runs
> `/bismillah setup #channel` once. About a minute. Guide:
> hadithbot.app/send-daily-hadith-discord
>
> Happy to jump on a call and set it up with you, or to leave it entirely — no
> pressure either way.
>
> Jazakum Allahu khayran,
> [YOUR NAME]

## Follow-up (once, after a week or so)

> Assalamu alaikum — just floating this back up in case it got buried. Totally
> fine if it's not for you, I won't bring it up again. Jazakum Allahu khayran.

## Announcement for after it's installed

Post this in the server so members know what the new bot is:

> Assalamu alaikum everyone — we've added **HadithBot** to #[CHANNEL]. Every
> evening it'll post a hadith with a link to its source, plus one of Allah's 99
> names with its meaning.
>
> You can also ask it for one any time:
> `/bismillah hadith` for a random hadith, `/bismillah name` for a name.
>
> It can't read your messages and doesn't know who any of you are — it just
> posts. May Allah make it a means of benefit for us all.

## Asking to be listed on the site

Once a community has been running it for a bit, they can ask to appear on the
wall at hadithbot.app. Send them the form:

> If you'd like [MSA NAME] on the site as one of the communities running it,
> there's a form here — takes ten seconds, and you can ask for it to come off
> any time: https://github.com/SaiyedRushan/HadithBot/issues/new?template=add-community.yml

Never add a community without that. The database knows every server the bot is
in, and the site deliberately doesn't read from it — the wall is fed by
`docs/data/communities.json`, which is only ever edited off the back of a
request. See the privacy policy, section 6.

## Adab notes

- Ask once, follow up once, then leave it.
- Don't post it in a server's general chat as if it's an announcement; go to
  whoever runs it.
- Don't overstate it. It posts a message a day — that's the whole thing.
- If someone declines, thank them properly. The intention is the reward.
