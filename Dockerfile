ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.10.8

# ---------------------------
# UV Image Alias Stage
# ---------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

# ---------------------------
# Builder Stage
# ---------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /app

# Enable bytecode compilation and ensure uv creates the venv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Use cache mounts to speed up re-builds
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev

# Copy uv binary directly from the official image
COPY --from=uv_image /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./

# Install dependencies
# --frozen: assert uv.lock is valid
# --no-dev: exclude dev deps (only main)
# --no-install-project: install only deps first (better layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# This is required so the package manager can install the package metadata
COPY museflow ./museflow

# Install the project package itself to create the .egg-info / dist-info metadata for importlib (name, version)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

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
