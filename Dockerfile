# Use Python 3.11 slim image (matches .python-version)
FROM python:3.11-slim

# Bring in the uv binary, pinned to match local dev and CI
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /bin/

WORKDIR /app

# System build deps (some wheels may need a compiler)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies from the lockfile (no dev group), using the
# image's Python 3.11 rather than letting uv download another interpreter.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --python python3.11

# Put the project venv on PATH so python resolves to it
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code (.dockerignore keeps the local .venv out)
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8080

# Health check (python:3.11-slim has no curl, so use stdlib urllib)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/',timeout=5).getcode()==200 else 1)" || exit 1

# Run the application. server.py runs the bot and serves the health check on
# :8080 from the same asyncio event loop. It used to be gunicorn, which was
# twice taken down by port scanners on 8080: first by killing the sync worker
# (47 bot reconnects in an hour on 2026-09-18), then by holding all four gthread
# threads with half-sent requests (health check dead for 2.5h on 2026-09-27).
# See the docstring at the top of server.py.
CMD ["python", "server.py"]
