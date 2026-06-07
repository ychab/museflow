# MuseFlow

![Python](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)
[![CI](https://github.com/ychab/museflow/actions/workflows/ci.yml/badge.svg)](https://github.com/ychab/museflow/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ychab/museflow/graph/badge.svg)](https://codecov.io/gh/ychab/museflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

MuseFlow is an assistant for your music provider account, built with Python, FastAPI and Typer.

Its main goal is to help you discover new music by providing recommendations based on your listening history.
MuseFlow fetches suggestions from various providers and curates them into new dedicated playlists.
A key feature is that it prioritizes artists and tracks that are **unknown to you**, ensuring true discovery rather than replaying your favorites.

For now, **only [Spotify](https://open.spotify.com/) is supported**.

## Requirements

To work with this project, you will need the following tools installed on your machine:

*   **Python**: 3.13
*   **UV**: 0.10.8
*   **Docker Compose**: v2

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

    Copy the example environment file and configure it with your settings.

    ```bash
    cp .env.DIST .env
    ```

    Open `.env` and fill in the required values:
    *   `SPOTIFY_CLIENT_ID`: Your Spotify App Client ID.
    *   `SPOTIFY_CLIENT_SECRET`: Your Spotify App Client Secret.
    *   `MUSEFLOW_SECRET_KEY`: A secret key for the application (min 32 characters).
    *   Database settings if you want to customize them (defaults are usually fine for local development with Docker).

2.  **Spotify App Configuration:**

    You must add the redirect URI to your Spotify App settings in the Developer Dashboard.

    *   Go to your app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
    *   Click on "Edit Settings".
    *   Under "Redirect URIs", add the callback URL.
    *   By default, the application uses: `http://127.0.0.1:8000/api/v1/spotify/callback`
    *   Ensure this matches the `SPOTIFY_REDIRECT_URI` in your `.env` configuration (or the default if not set).

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

## Getting Started

Once the application is running and configured, here is the typical flow to go from zero to discovering new music:

```bash
# 1. Create a user account
uv run museflow users create --email user@example.com

# 2. Connect your Spotify account (requires the API server to be running)
uv run museflow spotify connect --email user@example.com

# 3. Import your full streaming history from Spotify's data export
uv run museflow spotify history --email user@example.com --directory ~/Downloads/MySpotifyData

# 4. Build your personal taste profile with AI analysis
uv run museflow taste build --email user@example.com

# 5. Discover new music and generate a playlist
uv run museflow discover --email user@example.com
```

Step 4 is optional but enriches the recommendations.

## CLI User Guide

MuseFlow provides a Command Line Interface (CLI) to manage users and interact with Spotify.

To use the CLI, you can use the `museflow` command if installed in your environment, or run it via UV:

```bash
uv run museflow [COMMAND]
```

### Global Options

*   `--log-level`, `-l`: Set the logging level (e.g., DEBUG, INFO, WARNING, ERROR).
*   `--log-handlers`: Set the logging handlers.
*   `--version`, `-v`: Show the application's version and exit.
*   `--help`: Show help message.

### User Management (`users`)

Manage application users.

**Create a user:**

```bash
uv run museflow users create --email <email>
```
You will be prompted to enter and confirm the password.

**Update a user:**

```bash
uv run museflow users update <user_id> --email <new_email> --password <new_password>
```

### Spotify Interaction (`spotify`)

Interact with Spotify data.

**Connect a user to Spotify:**

Initiates the OAuth flow. You need to open the URL in a browser and authorize the app.

**Prerequisite:** The FastAPI application must be running to handle the Spotify callback.
Ensure you have started the application (e.g., using `make up`) before running this command.

```bash
uv run museflow spotify connect --email <email>
```

*   `--timeout`: Seconds to wait for authentication (default: 60.0).
*   `--poll-interval`: Seconds between status checks (default: 2.0).

**Import streaming history:**

Imports a user's extended streaming history from the JSON files exported via Spotify's [privacy data request](https://www.spotify.com/account/privacy/). Parses all JSON files in the given directory, deduplicates track IDs, fetches unknown tracks from Spotify, and upserts them into the database.

**Prerequisite:** Export your data from Spotify (Account → Privacy Settings → Request your data) and unzip the archive. Only the `Streaming_History_Audio_*.json` files are used.

```bash
uv run museflow spotify history --email <email> --directory <path/to/history/folder> [OPTIONS]
```

**History Options:**

*   `--directory`: Path to the directory containing the Spotify streaming history JSON files (**required**).
*   `--min-duration-played`: Minimum playback duration in seconds to count a track as played (default: 90).
*   `--batch-size`: Number of tracks to fetch from Spotify and upsert per batch, between 1 and 50 (default: 20).
*   `--fetch-bulk` / `--no-fetch-bulk`: Use the Spotify bulk tracks endpoint instead of per-track requests. The bulk endpoint is deprecated by Spotify and may be removed in the future (default: no fetch-bulk).
*   `--purge` / `--no-purge`: Purge all existing history tracks before importing (default: no purge).

Example: Import history, ignoring plays shorter than 30 seconds

```bash
uv run museflow spotify history --email user@example.com --directory ~/Downloads/MySpotifyData --min-duration-played 30
```

On completion, a summary table is printed showing items read, items skipped, unique track IDs found, and tracks created.

### Taste Profile (`taste`)

Build and manage your personal taste profile using AI analysis of your library.

#### `taste build`

Analyzes your imported library tracks with Gemini AI to generate a master taste profile — including era breakdowns, personality archetype, and life-phase insights.

**Prerequisite:** You must have imported your streaming history first (via `spotify history`).

```bash
uv run museflow taste build --email <email> [OPTIONS]
```

**Options:**

*   `--track-limit`: Maximum number of seed tracks used to build the profile (default: 3000, max: 20000).
*   `--batch-size`: Number of tracks sent per Gemini batch (default: 400, max: 1000).

Example: Build a taste profile for a user

```bash
uv run museflow taste build --email user@example.com
```

On completion, the command prints the number of tracks processed, the profiler model and logic version, the number of musical eras detected, the personality archetype, and any life-phase insights.

### Discover (`discover`)

Discovers new music guided by your AI taste profile and creates a new playlist. Uses your full taste profile to generate contextually-aware recommendations — factoring in era, mood, genre preferences, and a configurable focus strategy.

**Prerequisite:** You must have built a taste profile first (via `taste build`).

```bash
uv run museflow discover --email <email> [OPTIONS]
```

**Options:**

*   `--advisor`: The AI advisor to use (default: `gemini`).
*   `--provider`: The music provider to use (default: `spotify`).
*   `--focus`: The discovery focus strategy (default: `expansion`). Controls how the advisor interprets your taste profile to generate suggestions.
*   `--name`: Taste profile name to use (defaults to the latest profile).
*   `--genre`: Optional genre hint for the advisor (e.g. `"jazz"`).
*   `--mood`: Optional mood hint for the advisor (e.g. `"melancholic"`).
*   `--custom-instructions`: Optional freeform instructions passed to the advisor.
*   `--similar-limit`: Number of recommended tracks to request from the advisor (default: `5`, max: `20`).
*   `--candidate-limit`: Maximum search candidates per suggestion (default: `10`, max: `20`).
*   `--playlist-size`: Target number of tracks in the generated playlist (default: `10`, max: `30`).
*   `--max-tracks-per-artist`: Maximum tracks per artist in the final playlist (default: `2`, max: `10`).
*   `--score-band-width`: Width of advisor score bands for tiebreaking by reconciler confidence (default: `0.05`, range: `0.01–0.5`).
*   `--dry-run`: Discover tracks without creating a playlist.

Example: Discover new music guided by your taste profile

```bash
uv run museflow discover --email user@example.com --focus expansion --playlist-size 15
```

Example: Discover jazz tracks with a melancholic mood

```bash
uv run museflow discover --email user@example.com --genre jazz --mood melancholic --dry-run
```

### Spotify Account Info (`spotify info`)

Displays diagnostic information about a user's Spotify account.

```bash
uv run museflow spotify info --email <email> [OPTIONS]
```

*   `--token` / `--no-token`: Display the current Spotify OAuth token (default: on).

## Development

**Linting and Formatting:**

```bash
make lint
```

**Running Tests:**

```bash
make test
```

## Claude Code

This project is configured for [Claude Code](https://claude.ai/claude-code), Anthropic's AI coding assistant. The configuration lives in:

- **`CLAUDE.md`** — project conventions and architecture rules loaded into every Claude session
- **`CONVENTIONS.md`** — detailed architecture reference (the source of truth)
- **`.claude/commands/`** — custom slash commands (skills) for common development workflows
- **`.claude/agents/`** — autonomous subagents for specialized tasks

### Skills

Skills are project-specific slash commands that encode the project's conventions so you don't have to repeat them. Invoke them in a Claude Code session with `/command-name [arguments]`.

| Skill | Invocation | What it does |
|-------|-----------|--------------|
| `/new-feature` | `/new-feature <name>` | Scaffolds a full feature across all layers: entity → input schema → port → use case → SQLAlchemy model → repository → API endpoint → CLI command → unit and integration tests |
| `/new-migration` | `/new-migration <description>` | Guides an Alembic migration: generates the file, reviews nullable defaults and `downgrade()`, verifies it runs cleanly |
| `/add-tests` | `/add-tests <file_path>` | Analyzes a source file and generates unit + integration tests targeting 100% branch coverage, reusing existing fixtures and factories |
| `/new-provider` | `/new-provider <name>` | Scaffolds a new music provider integration: client, session, library adapter, DTOs, mappers, schemas, types, exceptions, settings, WireMock stubs, and tests — mirroring the Spotify pattern |
| `/arch-review` | `/arch-review [files]` | Reviews changed files for Clean Architecture violations: framework imports in domain, repositories instantiated in use cases, wrong `JSONB`/`ARRAY` dialect, missing `to_entity()`, logging secrets, etc. |
| `/security-review` | `/security-review [files]` | Reviews changed files for security issues: hardcoded secrets, unprotected endpoints, unbounded `Retry-After` sleeps, raw SQL, missing input validation, path traversal, and runs `uv audit` for CVEs |

### Agents

Agents are autonomous subagents that Claude routes to automatically or that you can trigger explicitly. They run as subprocesses with their own tools and specialized instructions.

| Agent | What it does |
|-------|--------------|
| `python` | Fixes lint errors autonomously — runs `make lint`, fixes ruff/mypy/deptry issues, iterates until clean |
| `test` | Fixes failing tests and fills coverage gaps — runs `make test`, traces failures, writes missing branches |
| `arch` | Architecture compliance review — checks changed files against hexagonal architecture rules |
| `security` | Security review — checks changed files for vulnerabilities, runs `uv audit` for CVEs |
| `engineer` | Read-only codebase explorer — explains feature flows, locates code, guides implementation approach |
