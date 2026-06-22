.PHONY: install dev dev-server test lint

install:  ## Install all deps (runtime + dev) into .venv
	uv sync

dev:  ## Autoreload the bot on save (nodemon-style; bot only)
	uv run watchmedo auto-restart --patterns='*.py' --recursive -- python bot.py

dev-server:  ## Autoreload the full server on save (bot + Flask /health)
	uv run watchmedo auto-restart --patterns='*.py' --recursive -- python server.py

test:  ## Run the test suite
	uv run pytest -q

lint:  ## Static checks (undefined names, bad imports)
	uv run pyflakes bot.py utils.py db.py server.py test_setup.py test_hadith_progression.py tests/
