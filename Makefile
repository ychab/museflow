.DEFAULT_GOAL := help


################
# Help
################

.PHONY: help
help:
	@grep -E '^[a-zA-Z0-9 -]+:.*## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


##############
# Dependencies
##############

.PHONY: install install-deps install-precommit update update-deps update-precommit lock outdated

install-deps:  ## Install python dependencies
	uv sync --all-groups

install-precommit:  ## Install pre-commit hooks
	uv run pre-commit install

install: install-deps install-precommit ## Install python dependencies and pre-commit hooks

update-deps:  ## Update python dependencies
	uv lock --upgrade
	uv sync --all-groups

update-precommit:  ## Update pre-commit hooks
	uv run pre-commit autoupdate

update: update-deps update-precommit ## Update python dependencies and pre-commit hooks

lock:  ## Lock dependencies
	uv lock

outdated: ## List outdated dependencies
	uv pip list --outdated


############
# Versioning
############

BUMP_TARGETS = bump-patch bump-minor bump-major

# This "phantom" target exists only to appear in 'make help'
bump: ## Bump version (options: bump-patch, bump-minor, bump-major)

.PHONY: $(BUMP_TARGETS) bump
$(BUMP_TARGETS): bump-%:
	uvx bump-my-version bump $*
	uv sync


########
# Docker
########

.PHONY: ps logs up up-db up-wiremock up-test down restart reload reset

ps:  ## List containers
	docker compose ps --all

logs:  ## Show container logs
	docker compose logs -f

up: ## Start containers
	docker compose up --detach --build --wait

up-db:  ## Start database container only
	docker compose up --detach --wait db

up-wiremock:  ## Start wiremock containers only
	docker compose up --detach --wait wiremock-spotify wiremock-openrouter

up-test: up-db up-wiremock  ## Start DB and Wiremock containers

down: ## Stop containers
	docker compose down --remove-orphans

restart: ## Restart containers
	docker compose restart

reload: down up ## Stop and start containers

reset:  ## Remove volumes and images
	docker compose down --remove-orphans --volumes --rmi local


#####
# App
#####

.PHONY: run app-shell

run: ## Run the application
	uv run fastapi dev museflow/infrastructure/entrypoints/api/main.py

app-shell: up ## Connect to the application shell
	docker compose exec app /bin/bash


##########
# Database
##########

.PHONY: db-upgrade db-downgrade db-revision db-shell db-dump db-restore

db-upgrade: up-db  ## Upgrade database
	uv run alembic upgrade head

db-downgrade: up-db  ## Downgrade database
	uv run alembic downgrade base

db-revision: up-db ## Create a new migration
	uv run alembic revision --autogenerate

db-shell: up-db ## Connect to the database shell
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

db-dump: up-db  ## Dump database to external_data/backups/TIMESTAMP.sql
	@mkdir -p external_data/backups
	@FILE="external_data/backups/$$(date +%Y%m%d-%H%M%S).sql" && \
	docker compose exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" --no-acl --no-owner "$$POSTGRES_DB"' > "$$FILE" && \
	echo "Database dumped to $$FILE"

db-restore: down up-db  ## Restore latest backup (or FILE=path)
	@FILE=$${FILE:-$$(ls -t external_data/backups/*.sql 2>/dev/null | head -1)} && \
	test -n "$$FILE" || (echo "No backup found in external_data/backups/" && exit 1) && \
	echo "Restoring $$FILE" && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $$POSTGRES_DB" > /dev/null' && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "CREATE DATABASE $$POSTGRES_DB" > /dev/null' && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" > /dev/null' < "$$FILE"


#########
# Backups
#########

# A schema change resets the database: export what a reset loses, reset, then import it back.
# Each value can be overridden on the command line or by an environment variable.
BACKUPS_ROOT ?= external_data/backups
BACKUP_DIR ?=
HISTORY_DIR ?= external_data/spotify_history
MUSEFLOW_CLI_DEFAULT_EMAIL ?= $(shell grep -E '^MUSEFLOW_CLI_DEFAULT_EMAIL=' .env 2>/dev/null | cut -d= -f2-)

.PHONY: backup-export backup-import db-reset

backup-export: up-db  ## Export ratings, blacklist, enrichment and taste profiles to BACKUP_DIR (default: a new dated directory)
	@DIR="$(BACKUP_DIR)"; DIR="$${DIR:-$(BACKUPS_ROOT)/$$(date +%Y%m%d-%H%M%S)}" && \
	mkdir -p "$$DIR" && \
	uv run museflow rate export --output "$$DIR/ratings.yaml" && \
	uv run museflow blacklist export --output "$$DIR/blacklist.yaml" && \
	uv run museflow enrich export --output "$$DIR/enrichment.yaml" && \
	uv run museflow taste export --output "$$DIR/taste.yaml" && \
	echo "Backup written to $$DIR"

db-reset: up-db  ## Drop and recreate the database, migrate, then create the user and connect the provider
	@test -n "$(MUSEFLOW_CLI_DEFAULT_EMAIL)" || (echo "No email: set MUSEFLOW_CLI_DEFAULT_EMAIL in .env" && exit 1)
	@printf "Drop the database and everything in it? [y/N] " && read answer && [ "$$answer" = "y" ] || (echo "Aborted." && exit 1)
	@docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $$POSTGRES_DB WITH (FORCE)" > /dev/null'
	@docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "CREATE DATABASE $$POSTGRES_DB" > /dev/null'
	uv run alembic upgrade head
	uv run museflow users create --email "$(MUSEFLOW_CLI_DEFAULT_EMAIL)"
	uv run museflow provider connect --email "$(MUSEFLOW_CLI_DEFAULT_EMAIL)"

backup-import: up-db  ## Import the streaming history (HISTORY_DIR), then BACKUP_DIR (default: the latest backup)
	@DIR="$(BACKUP_DIR)"; DIR="$${DIR:-$$(ls -td $(BACKUPS_ROOT)/*/ 2>/dev/null | head -1)}"; DIR="$${DIR%/}" && \
	test -n "$$DIR" || (echo "No backup found in $(BACKUPS_ROOT)/" && exit 1) && \
	echo "Importing $$DIR" && \
	uv run museflow tracks history --directory "$(HISTORY_DIR)" && \
	uv run museflow rate import --input "$$DIR/ratings.yaml" && \
	uv run museflow blacklist import --input "$$DIR/blacklist.yaml" && \
	uv run museflow enrich import --input "$$DIR/enrichment.yaml" && \
	uv run museflow taste import --input "$$DIR/taste.yaml"


################
# Testing
################

.PHONY: test test-unit test-integration

test: up-db up-wiremock ## Run all the testsuite
	uv run pytest ./tests -n auto --dist=loadgroup || ($(MAKE) down && exit 1)
	@$(MAKE) down

test-unit: ## Run unit tests
	uv run pytest ./tests/unit -n auto --dist=loadgroup -v

test-integration: up-test ## Run integration tests
	uv run pytest ./tests/integration -n auto --dist=loadgroup -v || ($(MAKE) down && exit 1)
	@$(MAKE) down

###################
# Local Development
###################

.PHONY: lint lint-format lint-check precommit

lint-format:  ## Lint and format code
	uv run ruff check museflow tests
	uv run ruff format museflow tests
	uv run mypy
	uv run deptry .
	uv run lint-imports

lint: lint-format

lint-check: ## Lint and check code
	uv run ruff check --no-fix museflow tests
	uv run ruff format --check museflow tests
	uv run mypy
	uv run deptry .
	uv run lint-imports

precommit: ## Run pre-commit hooks
	uv run pre-commit run --all-files

########
# Docs
########

.PHONY: docs-serve docs-build

docs-serve:  ## Serve the documentation locally with live reload
	uv run zensical serve

docs-build:  ## Build the documentation site (strict mode)
	uv run zensical build --clean --strict


clean: ## Cleanup cache files
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov coverage.xml junit.xml site
	rm -f .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
