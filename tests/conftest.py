"""Let the suite import modules that reach the database at import time.

db.py raises on import when SUPABASE_URL is unset and builds a client straight
away, so anything importing it -- bot.py included -- is unimportable on a
machine without credentials. That is every CI runner, and it took the pipeline
down once already.

These are deliberately unusable values. Tests must not touch a real database,
so pointing at a .invalid host means a test that tries will fail loudly rather
than quietly reading production. setdefault, not assignment, so a developer
with a real .env still gets these placeholders here: load_dotenv() does not
override what is already set, and conftest runs first.
"""

import os

os.environ.setdefault("SUPABASE_URL", "https://tests-must-not-hit-the-db.invalid")
os.environ.setdefault("SUPABASE_KEY", "not-a-real-key")
