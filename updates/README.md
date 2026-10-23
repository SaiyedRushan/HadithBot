# Update messages

Each `YYYY-MM-DD.md` file here is one message, posted exactly as written
(Discord markdown, 2000 characters at most). On that date the daily broadcast
posts it in every channel, just before the 6:00 PM hadith. So the file's date
is the day it goes out, and it goes out once.

1. Write the file, dated the day you want it sent, and run
   `make update-preview` to check the text, its length, the date it goes out and
   which channels get it.
2. Optionally, `make update-test CHANNEL=<channel id>` posts a test copy to one
   channel with the production bot, so you can see it in Discord first.
3. Merge it to `main` the day before, or at least 15 minutes before 6:00 PM
   Toronto time on its date. Pushing a file here redeploys the bot, which is
   what puts it in the running container, and a bot that is restarting at
   6:00 PM misses that day's broadcast for every server.

`/bismillah send-now` runs the daily broadcast for one channel, so on an
update's date it posts the update there too.
