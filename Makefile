.PHONY: install dev dev-server test lint format

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
