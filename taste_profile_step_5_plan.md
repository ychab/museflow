# Step 5: CLI + Dependencies + Exports

**Part of:** [Master Plan](taste_profile_master_plan.md)
**Dependencies:** Steps 1–4 all complete (entity, use case, repo, adapter all exist)

## Files to touch

| Action | File |
|---|---|
| Create | `museflow/infrastructure/entrypoints/cli/commands/profile.py` |
| Modify | `museflow/infrastructure/entrypoints/cli/dependencies.py` |
| Modify | `museflow/infrastructure/entrypoints/cli/main.py` (or wherever the Typer app is assembled) |

## Before starting — read these files

- `museflow/infrastructure/entrypoints/cli/dependencies.py` — how existing context managers are structured (`get_gemini_client`, `get_track_repository`, etc.)
- `museflow/infrastructure/entrypoints/cli/commands/discover.py` (or similar) — how a command calls `anyio.run(...)` and uses the dependency helpers

## 1. `museflow/infrastructure/entrypoints/cli/dependencies.py` — add two helpers

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from museflow.infrastructure.adapters.advisors.gemini.taste_profile_client import GeminiTasteProfileAdapter
from museflow.infrastructure.adapters.database.repositories.taste_profile import UserTasteProfileSQLRepository
from museflow.infrastructure.config.settings.gemini import gemini_settings


@asynccontextmanager
async def get_gemini_taste_profile_client() -> AsyncGenerator[GeminiTasteProfileAdapter, None]:
    client = GeminiTasteProfileAdapter(
        api_key=gemini_settings.api_key.get_secret_value(),
        model=gemini_settings.model,
        base_url=str(gemini_settings.base_url),
        timeout=gemini_settings.http_timeout,
        verify_ssl=gemini_settings.http_verify_ssl,
        max_retry_wait=gemini_settings.http_max_retry_wait,
    )
    try:
        yield client
    finally:
        await client.close()


def get_taste_profile_repository(session: AsyncSession) -> UserTasteProfileSQLRepository:
    return UserTasteProfileSQLRepository(session)
```

## 2. `museflow/infrastructure/entrypoints/cli/commands/profile.py` — new command file

```python
from __future__ import annotations

from typing import Annotated

import anyio
import typer

app = typer.Typer()


@app.command("build")
def profile_build(
    email: Annotated[str, typer.Option(help="User email address")],
    track_limit: Annotated[int, typer.Option(help="Max tracks to process")] = 3000,
    batch_size: Annotated[int, typer.Option(help="Tracks per Gemini batch")] = 400,
) -> None:
    """Build a Gemini master taste profile from your library."""
    anyio.run(_profile_build_logic, email, track_limit, batch_size)


async def _profile_build_logic(email: str, track_limit: int, batch_size: int) -> None:
    from museflow.application.inputs.taste_profile import BuildTasteProfileConfigInput
    from museflow.application.use_cases.build_taste_profile import BuildTasteProfileUseCase
    from museflow.infrastructure.entrypoints.cli.dependencies import (
        get_async_session,
        get_gemini_taste_profile_client,
        get_taste_profile_repository,
        get_track_repository,
        get_user_by_email,
    )

    async with get_async_session() as session:
        user = await get_user_by_email(session, email)
        track_repo = get_track_repository(session)
        profile_repo = get_taste_profile_repository(session)

        async with get_gemini_taste_profile_client() as advisor:
            use_case = BuildTasteProfileUseCase(
                track_repository=track_repo,
                profile_repository=profile_repo,
                advisor=advisor,
            )
            config = BuildTasteProfileConfigInput(track_limit=track_limit, batch_size=batch_size)
            profile = await use_case.build_profile(user, config)

    # Output summary
    typer.echo(f"Profile built: {profile.tracks_count} tracks processed")
    typer.echo(f"Advisor: {profile.advisor} ({profile.logic_version})")
    typer.echo(f"Eras: {len(profile.profile['taste_timeline'])}")
    if profile.profile["personality_archetype"]:
        typer.echo(f"Archetype: {profile.profile['personality_archetype']}")
    for insight in profile.profile["life_phase_insights"]:
        typer.echo(f"  - {insight}")
```

## 3. Register `profile` subgroup in main CLI app

Read the main Typer app file (likely `museflow/infrastructure/entrypoints/cli/main.py` or similar) and add:

```python
from museflow.infrastructure.entrypoints.cli.commands.profile import app as profile_app

app.add_typer(profile_app, name="profile")
```

## Verification

```bash
make lint
muse profile --help           # should show "build" command
muse profile build --help     # should show all options
```

Integration test (after WireMock stubs are in place):
- `tests/integration/application/use_cases/test_build_taste_profile.py`
  - `test__build_profile__nominal` — full flow with mocked Gemini via WireMock
  - Verify DB row exists after run
  - Verify upsert on second run (updated_at changes, row count stays 1)
