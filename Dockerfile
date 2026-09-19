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

# Put the project venv on PATH so gunicorn/python resolve to it
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

# Run the application.
#
# gthread, not the default sync worker. The Discord bot runs in a thread inside
# this worker (see server.py), so anything that kills the worker reconnects the
# bot -- and a sync worker is trivially easy to kill: it blocks in recv() on an
# accepted connection, and while it's blocked it doesn't touch its heartbeat
# file, so the arbiter murders it after --timeout. A port scanner opening a
# socket to 8080 and never sending a request is enough. That reconnected the
# bot 47 times in one hour on 2026-09-18. gthread notifies its heartbeat
# from the main accept loop, so one silent connection stalls one thread and
# nothing else.
#
# --timeout 120 rather than the default 30 because the only thing this worker
# serves is a health check; a slow response is not worth a reconnect.
CMD ["gunicorn", \
     "--worker-class", "gthread", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "-b", "0.0.0.0:8080", \
     "server:app"]
