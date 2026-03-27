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
	docker compose up --detach --wait wiremock-spotify wiremock-lastfm wiremock-gemini

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
	docker compose exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" --no-acl --no-owner "$$POSTGRES_DB"' > "$$FILE"

db-restore: up-db  ## Restore latest backup (or FILE=path)
	@FILE=$${FILE:-$$(ls -t external_data/backups/*.sql 2>/dev/null | head -1)} && \
	test -n "$$FILE" || (echo "No backup found in external_data/backups/" && exit 1) && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $$POSTGRES_DB" > /dev/null' && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d postgres -c "CREATE DATABASE $$POSTGRES_DB" > /dev/null' && \
	docker compose exec -T db sh -c 'psql -q -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" > /dev/null' < "$$FILE"


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

lint: lint-format

lint-check: ## Lint and check code
	uv run ruff check --no-fix museflow tests
	uv run ruff format --check museflow tests
	uv run mypy
	uv run deptry .

precommit: ## Run pre-commit hooks
	uv run pre-commit run --all-files

clean: ## Cleanup cache files
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov coverage.xml junit.xml
	rm -f .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +

repomix:
	npx repomix@latest --no-security-check --compress
