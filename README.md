cp .env.DIST .env  # use direnv instead?
poetry install
poetry run pre-commit install
make up
