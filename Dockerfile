ARG PYTHON_VERSION=3.13

# ---------------------------
# Builder Stage
# ---------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG POETRY_VERSION=1.8.5

ENV POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    PIP_NO_CACHE_DIR=1

ENV PATH="$POETRY_HOME/bin:$PATH"

# Use cache mounts to speed up re-builds
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Mount poetry cache to speed up dependency installation (excluding the project itself first)
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-root

# This is required so poetry can install the package metadata
COPY museflow ./museflow

# Install the project package itself to create the .egg-info / dist-info metadata for importlib
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main

# ---------------------------
# Final Stage
# ---------------------------
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install runtime deps only (libpq5) + curl for healthcheck
# Again, using cache mounts and no-install-recommends
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser museflow ./museflow

USER appuser

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "museflow.infrastructure.entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
