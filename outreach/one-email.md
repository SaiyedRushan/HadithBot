# The one-email option

Lowest effort path: one plain email, your address in To, 52 MSAs in BCC. About
ten minutes of work. What to expect from it is at the bottom.

## Subject

> A free bot that posts a daily hadith in your Discord

## Body

> Assalamu alaikum wa rahmatullah,
>
> My name is Rushan. I'm a York University alum and I made a Discord bot called
> HadithBot. Every evening it posts one hadith with a link to its source
> on Sunnah.com, and one of the 99 names of Allah with its meaning. Members can
> also ask it for one any time with a slash command.
>
> I'm sending this to a few dozen MSAs at once, so sorry that it isn't written
> just for you. I wanted to keep it short. If you're not the person who runs
> your Discord, could you pass it to whoever is?
>
> It's free and open source, and I pay for the hosting myself. It can't read
> any messages in your server. It runs without Discord's message content and
> server members intents, so Discord doesn't even send it the text of what
> people say. All it stores is which channel to post in and which hadith it
> left off at.
>
> Setup takes about a minute. Someone with Manage Server adds it from
> hadithbot.app, then runs `/bismillah setup #channel` once.
>
> Site: hadithbot.app
> Privacy policy: hadithbot.app/privacy
> Code: github.com/SaiyedRushan/HadithBot
>
> I built it for the York MSA while I was there and it's still running in their
> server. If it'd be useful for yours, I'm happy to hop on a call and set it up
> with you. If not, no problem at all, and you won't hear from me again.
>
> Jazakum Allahu khayran,
> Rushan

Add your Instagram or phone under your name if you're comfortable with it. A
student exec is far more likely to reply to a person they can look up than to
an email address on its own.

## The BCC line

49 addresses, all from the `confirmed` and `likely` rows of
[`msa-contacts.csv`](msa-contacts.csv). This block is the post-bounce version:
the three that failed on the 20 Sep send have been taken out. Copy it into BCC:

```
msa@utmsu.ca, msa@uoguelph.ca, senecamsaofficial@gmail.com, askmsaubc@gmail.com, gmumsa@googlegroups.com, msaexec@duke.edu, umcpmsa@gmail.com, msaatsu@gmail.com, gatechmuslimstudentassociation@gmail.com, vcumsa@gmail.com, runewarkmsa@gmail.com, muslimstudentsassociation@njms.rutgers.edu, msa@binghamtonsa.org, cumuslims@gmail.com, msaasu@gmail.com, board@pennmsa.com, umassmsa@gmail.com, info@uconnmsa.com, uofrmsa@gmail.com, und.msa@und.edu, msagsdm@bu.edu, uicmsa@gmail.com, msauiuc1@gmail.com, lucmsapr@gmail.com, msa@iit.edu, dpu.umma@gmail.com, msa.benedictine@gmail.com, elmhurstu.msa@gmail.com, msapurdue@gmail.com, msabloomington@gmail.com, iupuimsa13@gmail.com, msa-eboard@umich.edu, msaofmsu@gmail.com, waynestatemsa@gmail.com, wmumsabroncos@gmail.com, msa.ohiostate@gmail.com, msa-exec@case.edu, ucincymsa@gmail.com, clestatemsa@gmail.com, utoledomsa@gmail.com, uwmad.msa@gmail.com, msauwm@outlook.com, muslimstudents.mu@gmail.com, muslimstudents.mizzou@gmail.com, msa@su.wustl.edu, msa.utd@gmail.com, tamumsa.brotherssocial@gmail.com, sdsu.msa@gmail.com, hi@sjsumsa.org
```

Left out on purpose: `President@uky.edu` is a placeholder in the source
directory, and `diwa.ahmadzai067@topper.wku.edu` is one student's school
address from a stale listing.

## What bounced on the 20 Sep send

Three out of 52, and not one of them was a spam block.

| Address | Code | What it means |
| --- | --- | --- |
| msa@utoronto.ca | 550 5.4.1 Access denied | The address exists. Their Exchange list is set to accept mail only from inside utoronto.ca, so no external sender can ever reach it. Not something to retry. |
| contact-msa@sfu.ca | 550 5.1.1 User unknown | Dead mailbox. The SFSS club directory still advertises it. |
| external@msaconcordia.ca | NXDOMAIN | The whole msaconcordia.ca domain has lapsed. They moved to Facebook and Linktree. |

The useful part is in the headers SFU bounced back. The original message passed
SPF, DKIM and DMARC, Microsoft scored it `compauth=pass reason=100` and
`SCL:1`, and marked it `SFV:NSPM`, which is their code for not spam. A lot of
these schools run Microsoft 365, so that is decent evidence the other 49 landed
in inboxes rather than junk.

Reach the three another way: U of T through the contact form or exec office
hours at uoftmsa.com/contact-us.html, SFU and Concordia through Instagram.

## Six things that decide whether it lands

- **Send from your normal Gmail.** Not a new address, not a noreply@ on the
  hadithbot.app domain. A fresh sender with no history blasting 52 recipients
  is the exact shape of spam. Your everyday account has years of reputation.
- **Gmail's free limit is 500 recipients a day**, so 52 in one send is fine.
- **Plain text. No images, no tracking pixel, no link shortener.** Write the
  URLs out as normal text like the draft does.
- **Tuesday to Thursday, morning.** Weekend sends sit unread until Monday and
  land under everything else.
- **Reply to bounces by hand.** Student org Gmail accounts rotate constantly, so
  expect a handful. A bounce from a big chapter is worth thirty seconds on
  their Instagram to find the current address.
- **Don't follow up on the blast.** `OUTREACH.md` says ask once, follow up once,
  and a follow-up to 52 people who ignored the first one is just a second blast.

## What this will actually get you

Cold email to a shared student org inbox replies at a few percent. Call it one
to three replies out of 52, and not every reply is a yes. That is a fine return
for ten minutes, so it's worth sending. Just don't read a quiet inbox as the
product being the problem.

The reason it's low is that most of these 52 don't run a Discord at all. UMD,
Duke, UW-Madison, UTD, UBC and McGill all show WhatsApp or GroupMe on their
pages. For them there is no yes available.

## The thing that will beat it

Seven MSAs have a public Discord you can walk into today: **GMU, Waterloo,
Carleton, UAlberta, McGill, RPI, NJIT.** Join the server, read it for five
minutes, then message whoever is obviously running it and say something true
about their server. That is maybe an hour of work for all seven and it will
almost certainly out-convert the blast, because you are talking to the one
person who can actually click add, in the place where the bot would live.

Invites and details are in [`msa-contacts.md`](msa-contacts.md).

Do both. Send the blast first, since it costs you nothing to have it running in
the background while you do the seven properly.

## Timing

Mid-September is good. Execs are still building out their servers for the year
and haven't hit midterms. It gets worse every week from here, so if you're going
to send it, send it this week.
