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

# A backup is a dated directory holding the full SQL dump (db-dump) and the YAML exports (backup-export).
# Each value can be overridden on the command line or by an environment variable.
BACKUPS_ROOT ?= external_data/backups
BACKUP_DIR ?=
HISTORY_DIR ?= external_data/spotify_history
# Computed once per make call: the dump and the exports of one backup-export share the directory.
NEW_BACKUP_DIR := $(or $(BACKUP_DIR),$(BACKUPS_ROOT)/$(shell date +%Y%m%d-%H%M%S))
LATEST_BACKUP_DIR = $(or $(BACKUP_DIR),$(patsubst %/,%,$(firstword $(shell ls -td $(BACKUPS_ROOT)/*/ 2>/dev/null))))

.PHONY: db-upgrade db-downgrade db-revision db-shell db-dump db-restore

db-upgrade: up-db  ## Upgrade database
	uv run alembic upgrade head

db-downgrade: up-db  ## Downgrade database
	uv run alembic downgrade base

db-revision: up-db ## Create a new migration
	uv run alembic revision --autogenerate

db-shell: up-db ## Connect to the database shell
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

db-dump: up-db  ## Dump database to BACKUP_DIR/db.sql (default: a new dated directory)
	@mkdir -p "$(NEW_BACKUP_DIR)"
	@docker compose exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" --no-acl --no-owner "$$POSTGRES_DB"' > "$(NEW_BACKUP_DIR)/db.sql"
	@echo "Database dumped to $(NEW_BACKUP_DIR)/db.sql"

db-restore: down up-db  ## Restore the latest dump, same schema only (or FILE=path)
	@FILE=$${FILE:-$$(ls -t $(BACKUPS_ROOT)/*/db.sql 2>/dev/null | head -1)} && \
	test -n "$$FILE" || (echo "No dump found in $(BACKUPS_ROOT)/" && exit 1) && \
	echo "Restoring $$FILE" && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $$POSTGRES_DB" > /dev/null' && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "CREATE DATABASE $$POSTGRES_DB" > /dev/null' && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" > /dev/null' < "$$FILE"


#########
# Backups
#########

# A schema change resets the database: export with the current code, reset, then import with the new one.

.PHONY: backup-export backup-import

backup-export: db-dump  ## Dump the database, then export ratings, blacklist, enrichment, taste profiles and LLM usage next to it
	@uv run museflow rate export --output "$(NEW_BACKUP_DIR)/ratings.yaml"
	@uv run museflow blacklist export --output "$(NEW_BACKUP_DIR)/blacklist.yaml"
	@uv run museflow enrich export --output "$(NEW_BACKUP_DIR)/enrichment.yaml"
	@uv run museflow taste export --output "$(NEW_BACKUP_DIR)/taste.yaml"
	@uv run museflow llm export --output "$(NEW_BACKUP_DIR)/llm-usage.yaml"
	@echo "Backup written to $(NEW_BACKUP_DIR)"

backup-import: db-upgrade  ## Migrate, import the streaming history (HISTORY_DIR), then the latest backup (or BACKUP_DIR)
	@test -n "$(LATEST_BACKUP_DIR)" || (echo "No backup found in $(BACKUPS_ROOT)/" && exit 1)
	@echo "Importing $(LATEST_BACKUP_DIR)"
	uv run museflow tracks history --directory "$(HISTORY_DIR)"
	uv run museflow rate import --input "$(LATEST_BACKUP_DIR)/ratings.yaml"
	uv run museflow blacklist import --input "$(LATEST_BACKUP_DIR)/blacklist.yaml"
	uv run museflow enrich import --input "$(LATEST_BACKUP_DIR)/enrichment.yaml"
	uv run museflow taste import --input "$(LATEST_BACKUP_DIR)/taste.yaml"
	uv run museflow llm import --input "$(LATEST_BACKUP_DIR)/llm-usage.yaml"


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
