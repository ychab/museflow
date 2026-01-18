.DEFAULT_GOAL := help


##############
# Dependencies
##############


.PHONY: install
install:
	poetry install

.PHONY: update
update:
	poetry update
	poetry run pre-commit autoupdate

.PHONY: lock
lock:
	poetry lock --no-update

.PHONY: outdated
outdated:
	poetry show --outdated


###################
# Local Development
###################


.PHONY: lint
lint:
	poetry run ruff check spotifagent tests
	poetry run ruff format spotifagent tests
	poetry run mypy
	poetry run deptry .

.PHONY: precommit-run
precommit:
	poetry run pre-commit run --all-files


############
# Versioning
############


BUMP_TARGETS = bump-patch bump-minor bump-major bump-prepatch bump-preminor bump-premajor bump-prerelease

.PHONY: $(BUMP_TARGETS)
$(BUMP_TARGETS): bump-%:
	poetry version $*
	poetry install


########
# Docker
########

.PHONY: ps
ps:
	docker compose ps --all

.PHONY: logs
logs:
	docker compose logs -f

.PHONY: up
up:
	docker compose up --detach --build --wait

.PHONY: up-db
up-db:
	docker compose up --detach --wait db

.PHONY: down
down:
	docker compose down --remove-orphans

.PHONY: restart
restart:
	docker compose restart

.PHONY: reload
reload: down up

.PHONY: reset
reset:  ## Remove volumes and images
	docker compose down --remove-orphans --volumes --rmi local


#####
# App
#####


.PHONY: run
run:
	poetry run fastapi dev spotifagent/infrastructure/entrypoints/api/main.py

.PHONY: app-shell
app-shell: up
	docker compose exec app /bin/bash


##########
# Database
##########

.PHONY: db-upgrade
db-upgrade: up-db
	poetry run alembic upgrade head

.PHONY: db-downgrade
db-downgrade: up-db
	poetry run alembic downgrade base

.PHONY: db-revision
db-revision: up-db
	poetry run alembic revision --autogenerate

.PHONY: db-shell
db-shell: up-db
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'


################
# Testing
################

.PHONY: test
test: up-db
	poetry run pytest ./tests || ($(MAKE) down && exit 1)
	@$(MAKE) down

.PHONY: test-unit
test-unit:
	poetry run pytest ./tests/unit -v

.PHONY: test-integration
test-integration: up-db
	poetry run pytest ./tests/integration -v || ($(MAKE) down && exit 1)
	@$(MAKE) down
