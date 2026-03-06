# Load .env file automatically (optional but recommended)
set dotenv-load := true

# Default goal: list available commands
default:
    @just --list

# =============================================================================
# Dependencies
# =============================================================================

# Install python dependencies
install-deps:
    uv sync --all-groups

# Install pre-commit hooks
install-precommit:
    uv run pre-commit install

# Install python dependencies and pre-commit hooks
install: install-deps install-precommit

# Update python dependencies
update-deps:
    uv lock --upgrade
    uv sync --all-groups

# Update pre-commit hooks
update-precommit:
    uv run pre-commit autoupdate

# Update python dependencies and pre-commit hooks
update: update-deps update-precommit

# Lock dependencies
lock:
    uv lock

# List outdated dependencies
outdated:
    uv pip list --outdated

# =============================================================================
# Versioning
# =============================================================================

# Bump version (part: patch, minor, major)
bump part:
    uvx bump-my-version bump {{part}}
    uv sync

# =============================================================================
# Docker
# =============================================================================

# List containers
ps:
    docker compose ps --all

# Show container logs
logs:
    docker compose logs -f

# Start containers
up:
    docker compose up --detach --build --wait

# Start database container only
up-db:
    docker compose up --detach --wait db

# Start wiremock containers only
up-wiremock:
    docker compose up --detach --wait wiremock-spotify

# Start DB and Wiremock containers
dev: up-db up-wiremock

# Stop containers
down:
    docker compose down --remove-orphans

# Restart containers
restart:
    docker compose restart

# Stop and start containers
reload: down up

# Remove volumes and images
reset:
    docker compose down --remove-orphans --volumes --rmi local

# =============================================================================
# App
# =============================================================================

# Run the application
run:
    uv run fastapi dev museflow/infrastructure/entrypoints/api/main.py

# Connect to the application shell
app-shell: up
    docker compose exec app /bin/bash

# =============================================================================
# Database
# =============================================================================

# Upgrade database
db-upgrade: up-db
    uv run alembic upgrade head

# Downgrade database
db-downgrade: up-db
    uv run alembic downgrade base

# Create a new migration
db-revision: up-db
    uv run alembic revision --autogenerate

# Connect to the database shell
db-shell: up-db
    docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# =============================================================================
# Testing
# =============================================================================

# Run all the testsuite
test: up-db up-wiremock
    -uv run pytest ./tests
    @just down

# Run unit tests
test-unit:
    uv run pytest ./tests/unit -v

# Run integration tests
test-integration: up-db up-wiremock
    -uv run pytest ./tests/integration -v
    @just down

# =============================================================================
# Local Development
# =============================================================================

# Lint and format code
lint-format:
    uv run ruff check --fix museflow tests
    uv run ruff format museflow tests
    uv run mypy .
    uv run deptry .

# Alias for lint-format
lint: lint-format

# Lint and check code (CI style)
lint-check:
    uv run ruff check --no-fix museflow tests
    uv run ruff format --check museflow tests
    uv run mypy .
    uv run deptry .

# Run pre-commit hooks
precommit:
    uv run pre-commit run --all-files

# Cleanup cache files
clean:
    rm -rf .pytest_cache
    rm -rf .mypy_cache
    rm -rf .ruff_cache
    rm -rf htmlcov coverage.xml junit.xml
    rm -f .coverage
    find . -type d -name "__pycache__" -exec rm -rf {} +
