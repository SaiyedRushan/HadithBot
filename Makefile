.PHONY: install dev dev-server test lint format site site-wall books \
        logs status deploy restart shell health errors sends grep stale \
        members update-preview update-test update-send help

help:  ## List the available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# Production host. Defined in ~/.ssh/config (HostName, User and IdentityFile),
# so these targets carry no IP or key path -- rebuilding the VM means editing
# that one Host entry, not this file.
VM ?= hadithbot
APP_DIR ?= ~/HadithBot

install:  ## Install all deps (runtime + dev) into .venv
	uv sync

dev:  ## Autoreload the bot on save (nodemon-style; bot only)
	uv run watchmedo auto-restart --patterns='*.py' --recursive -- python bot.py

dev-server:  ## Autoreload the full server on save (bot + /health on :8080)
	uv run watchmedo auto-restart --patterns='*.py' --recursive -- python server.py

test:  ## Run the test suite
	uv run pytest -q

lint:  ## Lint (undefined names, bad imports, style) -- ruff
	uv run ruff check .

format:  ## Auto-format and fix lint issues -- ruff
	uv run ruff format . && uv run ruff check --fix .

site:  ## Regenerate the site's usage counts and community wall (needs SUPABASE_*)
	uv run python update_site.py

site-wall:  ## Regenerate just the community wall, without touching the database
	uv run python update_site.py --no-stats

books:  ## Regenerate the site's books & chapters reference (needs SUPABASE_*)
	uv run python update_books_page.py

# --- production (all over ssh; see the VM variable above) --------------------

logs:  ## Tail the live bot logs on the VM (Ctrl-C to stop)
	ssh -t $(VM) 'cd $(APP_DIR) && docker compose logs -f --tail 100'

status:  ## Is the bot up? Container state + the last few log lines
	@ssh $(VM) 'cd $(APP_DIR) && docker compose ps && echo && docker compose logs --tail 5'

health:  ## Ask the running bot for its own health (gateway state, guild count)
	@ssh $(VM) 'curl -s localhost:8080/health' && echo

errors:  ## Just the errors and warnings from the last day
	@ssh $(VM) 'cd $(APP_DIR) && docker compose logs --since 24h 2>&1 | grep -iE "error|warning|traceback|failed" | tail -40' \
	  || echo "no errors in the last 24h"

sends:  ## What the last daily broadcast actually did (per channel)
	@ssh $(VM) 'cd $(APP_DIR) && docker compose logs --since 48h 2>&1 | grep -iE "successfully sent|no hadith data|not found|failed to send" | tail -30' \
	  || echo "no delivery activity in the last 48h"

grep:  ## Search the logs: make grep Q=<pattern> (add SINCE=72h to widen; h/m/s only, not 7d)
	@test -n "$(Q)" || { echo 'usage: make grep Q=<pattern> [SINCE=24h]'; exit 2; }
	@ssh $(VM) 'cd $(APP_DIR) && docker compose logs --since $(or $(SINCE),24h) 2>&1 | grep -iE "$(Q)" | tail -50'

stale:  ## Which active channels missed their daily message? (runs locally)
	uv run python check_stale_channels.py

# Runs on the VM because it needs the production bot token to see the real
# servers; the local .env holds the dev bot, which is in neither of them.
members:  ## Refresh the stored server names and member counts from Discord
	ssh $(VM) 'cd $(APP_DIR) && docker compose exec -T hadithbot python backfill_channel_names.py'

# Update messages (see updates/README.md). The send targets run on the VM for
# the production token; the file goes in over stdin because the image has no
# .md files. git pull first so the newest update file is there.
LATEST_UPDATE = $$(ls updates/[0-9]*.md | sort | tail -1)

update-preview:  ## Show the newest update message, its length and who gets it
	uv run python send_update.py

update-test:  ## Post the newest update to one channel: make update-test CHANNEL=<id>
	@test -n "$(CHANNEL)" || { echo 'usage: make update-test CHANNEL=<channel id>'; exit 2; }
	ssh $(VM) 'cd $(APP_DIR) && git pull --ff-only -q && f=$(LATEST_UPDATE) && echo "Sending $$f" && docker compose exec -T hadithbot python send_update.py --send --channel $(CHANNEL) --file - < $$f'

update-send:  ## Post the newest update to every active channel
	ssh $(VM) 'cd $(APP_DIR) && git pull --ff-only -q && f=$(LATEST_UPDATE) && echo "Sending $$f" && docker compose exec -T hadithbot python send_update.py --send --file - < $$f'

deploy:  ## Pull main and rebuild on the VM (CI does this on push; use to force)
	ssh $(VM) 'cd $(APP_DIR) && git pull --ff-only && docker compose up -d --build && docker image prune -f'

restart:  ## Restart the container without rebuilding
	ssh $(VM) 'cd $(APP_DIR) && docker compose restart'

shell:  ## SSH into the VM
	ssh $(VM)
