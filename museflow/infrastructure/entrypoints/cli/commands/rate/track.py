import asyncio
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.rate import track_rate
from museflow.domain.exceptions import RateScoreInvalidException
from museflow.domain.exceptions import TrackNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.types import DISCOVERY_TRACK_SCORE_MIN
from museflow.infrastructure.entrypoints.cli.commands.rate import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("track", help="Rate a single track.")
def rate_track(
    track_id: uuid.UUID = typer.Argument(..., help="Track UUID to rate"),
    score: int = typer.Argument(..., help=f"Score ({DISCOVERY_TRACK_SCORE_MIN}-{DISCOVERY_TRACK_SCORE_MAX})"),
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    try:
        asyncio.run(rate_track_logic(track_id=track_id, score=score, email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TrackNotFoundError as e:
        typer.secho(f"Track {track_id} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except RateScoreInvalidException as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Track {track_id} rated {score}/10.", fg=typer.colors.GREEN)


async def rate_track_logic(track_id: uuid.UUID, score: int, email: EmailStr) -> None:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        await track_rate(
            track_id=track_id,
            score=score,
            user_id=user.id,
            track_repository=track_repository,
        )
