# MSA contact list

Research pass done 2026-08-14. Raw data lives in [`msa-contacts.csv`](msa-contacts.csv)
(115 rows). This file is the reading version: who to hit first and why.

Message templates are in [`../OUTREACH.md`](../OUTREACH.md) — the "Short DM — an
MSA you don't know" one is the right register for cold contact, and the longer
one for email.

## TL;DR

- **115 MSAs** across the US and Canada (20 Canadian). **53 have an email
  address**, 106 have a website; the rest are Instagram-only leads.
- **7 have a public Discord server** — those are the only ones where the bot has
  somewhere to go on day one. Start there.
- Everything else needs a two-step ask: do you have a Discord, and if so, can I
  put this in it. Half of MSAs run on WhatsApp or GroupMe instead, and for them
  the answer is just no.
- Biggest single lever isn't in the list: **MSA National** (~600 affiliated
  chapters, msanational.org/contact). One yes there is worth fifty cold emails.

## Tier 1 — has a public Discord (ask directly)

These are worth a real message. The Discord link is public, so you can see the
server before you write.

| MSA | Discord | Email | Notes |
| --- | --- | --- | --- |
| George Mason University | [invite](https://discord.com/invite/qsdX6WPwGF) | gmumsa@googlegroups.com | Discord is their main hub; new members `/apply` in `#start-here`. Has a real email too — best target on the list. |
| University of Waterloo | [invite](https://discord.gg/nQZtrhxJsX) | — | Big, active, Canadian. Contact via IG @uwmsa. |
| Carleton University (CUMSA) | [invite](https://discord.com/invite/uVmpsVNauU) | — | ~1.2k members. cumsa.ca |
| University of Alberta | [invite](https://discord.com/invite/QRZmXvy) | — | ~1.2k members. |
| McGill University | [invite](https://discord.gg/jEtmHXQf) | — | Discord + WhatsApp, both on linktr.ee/msamcgill |
| Rensselaer (RPI) | [invite](https://discord.gg/EdBXckprCC) | board emails on site | Site literally says Discord is "our main way of communication." |
| NJIT | [invite](https://discord.gg/jjdtUf4) | — | njitmsa.com |

Two more that almost certainly have one but I couldn't capture the link:
**Kennesaw State** (Discord on their Linktree) and **Mission College**.

## Tier 2 — solid email, Discord unknown

Straight from the org's own contact page, so these should be live. Worth the
longer email template. Roughly in order of chapter size / likelihood.

University of Toronto `msa@utoronto.ca` · Duke `msaexec@duke.edu` · UMD
`umcpmsa@gmail.com` · Georgia Tech `gatechmuslimstudentassociation@gmail.com` ·
UIC `uicmsa@gmail.com` · UT Dallas `msa.utd@gmail.com` · Binghamton
`msa@binghamtonsa.org` · CU Boulder `cumuslims@gmail.com` · ASU
`msaasu@gmail.com` · UPenn `board@pennmsa.com` · VCU `vcumsa@gmail.com` ·
Syracuse `msaatsu@gmail.com` · UBC `askmsaubc@gmail.com` · Guelph
`msa@uoguelph.ca` · UTM `msa@utmsu.ca` · Seneca `senecamsaofficial@gmail.com` ·
Rutgers–Newark `runewarkmsa@gmail.com` · Texas A&M
`tamumsa.brotherssocial@gmail.com`

## Tier 3 — email from a directory, verify before sending

These came out of a regional MSA directory
([docs.superhuman.com/@mmmusa/msa-database](https://docs.superhuman.com/@mmmusa/msa-database),
covering the Midwest) or a search snippet rather than the org's own live page.
The addresses look right but student orgs rotate gmail accounts constantly.
Send to these last, and treat a bounce as normal.

Michigan, Michigan State, Wayne State, WMU, Ohio State, Case Western,
Cincinnati, Cleveland State, Toledo, Purdue, IU Bloomington, IUPUI, UW-Madison,
UW-Milwaukee, Marquette, Mizzou, WUSTL, UIUC, Loyola Chicago, Illinois Tech,
DePaul, Benedictine, Elmhurst, SDSU, SJSU, UMass Amherst, UConn, Rochester,
UND, BU Dental, Rutgers NJMS, SFU, Concordia.

That directory is the single best find of this pass — it has clean
email/Instagram/website rows for ~40 Midwest chapters. If you want more volume,
the same shape of document probably exists for other MSA zones; worth asking
MSA National for.

## Tier 4 — leads only (website or Instagram, no email)

Large chapters where the only door is a contact form or an Instagram DM. Listed
in the CSV with `confidence=partial` or `lead-only`. Notable ones: UCLA,
Berkeley, UCSD, UC Davis, UCR, UCSB, UCI, Rutgers–New Brunswick, McMaster,
Western, TMU, UCalgary, Columbia, NYU, Princeton, Penn State, Virginia Tech,
GWU, Stony Brook, UMN, UT Austin, UW Seattle.

For these the realistic move is Instagram DM, not email — that's where their
exec actually reads messages.

## Things worth knowing before you send anything

- **Only someone with Manage Server can add a bot.** A `contact@` gmail is read
  by whoever has the password, often a comms officer, not the person who runs
  the Discord. Expect a forward, and make the message easy to forward.
- **Time it.** Late August through September is when execs are actively
  building out the server for the new year. Mid-terms is dead air.
- **Half of these run on WhatsApp or GroupMe**, not Discord — UMD, Duke,
  UW-Madison, UTD, UBC, McGill all show WhatsApp/GroupMe on their pages. For
  them the honest answer is that HadithBot isn't relevant yet, and pushing it
  wastes both sides' time.
- Exec addresses that are a person's name (`asedik@wisc.edu`,
  `diwa.ahmadzai067@topper.wku.edu`, RPI's board list) go stale every May.
  Prefer the role address whenever one exists.
- Two entries are junk on purpose so you don't waste a send: UK's
  `President@uky.edu` is a directory placeholder, and Instagram `@tmu_msa` is
  **Taipei Medical University**, not Toronto Metropolitan.

## On doing this at scale

`OUTREACH.md` says one message, to the right person, ask once and follow up
once. A 118-row spreadsheet makes it very easy to stop doing that. A hundred
identical emails sent in a morning is a cold campaign no matter how the message
is worded, and it'll get the domain filed as spam by the schools that share
mail infrastructure.

What actually works with this list: pick the tier 1 seven, write each one
individually with something specific about their server in it, and see what
comes back before touching tier 2.
