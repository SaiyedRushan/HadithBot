.PHONY: install dev dev-server test lint format site site-wall books \
        logs status deploy restart shell health

# Production host. Defined in ~/.ssh/config (HostName, User and IdentityFile),
# so these targets carry no IP or key path -- rebuilding the VM means editing
# that one Host entry, not this file.
VM ?= hadithbot
APP_DIR ?= ~/HadithBot

install:  ## Install all deps (runtime + dev) into .venv
	uv sync

dev:  ## Autoreload the bot on save (nodemon-style; bot only)
	uv run watchmedo auto-restart --patterns='*.py' --recursive -- python bot.py

dev-server:  ## Autoreload the full server on save (bot + Flask /health)
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

deploy:  ## Pull main and rebuild on the VM (CI does this on push; use to force)
	ssh $(VM) 'cd $(APP_DIR) && git pull --ff-only && docker compose up -d --build && docker image prune -f'

restart:  ## Restart the container without rebuilding
	ssh $(VM) 'cd $(APP_DIR) && docker compose restart'

shell:  ## SSH into the VM
	ssh $(VM)
