# Update messages

Each `YYYY-MM-DD.md` file here is one message the bot posts to every active
channel, exactly as written (Discord markdown, 2000 characters at most). The
newest file is the one that gets sent.

1. Write the file and run `make update-preview` to check the text, its length
   and the list of channels it would go to.
2. Merge it to `main`.
3. `make update-test CHANNEL=<channel id>` posts it to one channel with the
   production bot, so you can see it in Discord first.
4. `make update-send` posts it to every active channel.

Nothing records which updates went out, so running `update-send` twice posts
the message twice.
