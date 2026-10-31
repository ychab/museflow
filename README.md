# MuseFlow

![Python](https://img.shields.io/badge/python-3.14-blue?logo=python&logoColor=white)
[![CI](https://github.com/ychab/museflow/actions/workflows/ci.yml/badge.svg)](https://github.com/ychab/museflow/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ychab/museflow/graph/badge.svg)](https://codecov.io/gh/ychab/museflow)
[![Docs](https://img.shields.io/badge/docs-ychab.github.io%2Fmuseflow-blue?logo=materialformkdocs&logoColor=white)](https://ychab.github.io/museflow/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

MuseFlow turns your own streaming history (exported through your GDPR right of access) into an AI taste profile, then generates **discovery** playlists of music you don't know yet, and **rediscovery** playlists of forgotten favourites from your own past. You rate tracks in a feedback loop instead of an algorithm guessing for you.

It is a personal project and a showcase, built with Python, FastAPI and Typer. For now, **only [Spotify](https://open.spotify.com/) is supported**.

## Documentation

Full documentation: **<https://ychab.github.io/museflow/>**

*   [Product](https://ychab.github.io/museflow/product/): why MuseFlow exists, the V1 → V2 pivot, lessons learned.
*   [User guide](https://ychab.github.io/museflow/user-guide/): install, import your history, generate playlists. See [Getting started](https://ychab.github.io/museflow/user-guide/) for the "first playlist" flow.
*   [Technical](https://ychab.github.io/museflow/technical/): hexagonal architecture, LLM pipeline, testing.

How this project is built with AI agents: [AI-assisted development](https://ychab.github.io/museflow/technical/ai-assisted-development/).

## Requirements

To work with this project, you will need the following tools installed on your machine:

*   **Python**: 3.14
*   **UV**: 0.13.5
*   **Docker Compose**: v2
*   **direnv**: For automatic environment variable loading ([install guide](https://direnv.net/docs/installation.html))

For the Spotify connector:

*   **Spotify Developer Account**: You need a Spotify account and access to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
*   **Spotify App**: Create an app in the Spotify Developer Dashboard to get a `Client ID` and `Client Secret`.

## Installation

Follow these steps to set up the project locally:

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/ychab/museflow
    cd museflow
    ```

2.  **Install dependencies:**

    You can install dependencies and pre-commit hooks in one go using the Makefile:

    ```bash
    make install
    ```

    Alternatively, you can install them manually:

    *   **Install dependencies:**
        ```bash
        make install-deps
        # OR
        uv sync --all-groups
        ```

    *   **Install pre-commit hooks:**
        ```bash
        make install-precommit
        # OR
        uv run pre-commit install
        ```

## Configuration

Before running the application, you need to configure the environment variables and your Spotify App.

1.  **Environment Variables:**

    Non-secret defaults are in `.envrc` and loaded automatically by `direnv` when you enter the project directory. You only need to supply secrets.

    ```bash
    # Copy the example secrets file and fill in your values
    cp .env.example .env

    # Allow direnv to load .envrc (one-time, per clone)
    direnv allow
    ```

    Open `.env` and fill in the required secrets:
    *   `SPOTIFY_CLIENT_ID`: Your Spotify App Client ID.
    *   `SPOTIFY_CLIENT_SECRET`: Your Spotify App Client Secret.
    *   `OPENROUTER_API_KEY`: Your OpenRouter API key.
    *   `MUSEFLOW_SECRET_KEY`: A secret key for the application (min 32 characters, generate with `openssl rand -hex 32`).

    Personal overrides (e.g. a non-standard `DATABASE_PORT`) can also be added to `.env` — they take precedence over `.envrc` defaults.

2.  **Spotify App Configuration:**

    You must add the redirect URI to your Spotify App settings in the Developer Dashboard.

    *   Go to your app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
    *   Click on "Edit Settings".
    *   Under "Redirect URIs", add the callback URL.
    *   By default, the application uses: `http://127.0.0.1:8000/api/v1/spotify/callback`
    *   Ensure this matches the `SPOTIFY_CLIENT_REDIRECT_URI` in your `.envrc` (default: `http://127.0.0.1:8000/api/v1/spotify/callback`).

## Running the Application

You can run the application and the database using Docker Compose or the provided Makefile.

**Using Makefile:**

*   **Start the whole stack (DB + App):**
    ```bash
    make up
    ```

*   **Run the API server locally (with hot reload):**
    ```bash
    make run
    ```
    *Note: You need to have the database running (`make up-db`).*

**Using Docker Compose directly:**

```bash
docker compose up -d
```

## Development

**Linting and Formatting:**

```bash
make lint
```

**Running Tests:**

```bash
make test
```

**Documentation (live preview):**

```bash
make docs-serve
```

## License

MIT, see [LICENSE](LICENSE).
