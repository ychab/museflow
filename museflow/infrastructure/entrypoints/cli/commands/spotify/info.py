import asyncio
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

from pydantic import EmailStr

import typer
from rich.pretty import Pretty

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.spotify import app
from museflow.infrastructure.entrypoints.cli.commands.spotify import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True)
class SpotifyInfoData:
    genres: list[str] = field(default_factory=list)
    token: OAuthProviderUserToken | None = None


@app.command()
def info(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    show_genres: bool = typer.Option(
        True,
        "--genres/--no-genre",
        help="Display the list of genres of the user.",
    ),
    show_token: bool = typer.Option(
        True,
        "--token/--no-token",
        help="Display the Spotify OAuth token of the user.",
    ),
) -> None:
    if not show_genres and not show_token:
        raise typer.BadParameter("At least one --show flag must be provided.")

    try:
        info_data = asyncio.run(info_logic(email=email, show_genres=show_genres, show_token=show_token))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if show_genres and info_data.genres:
        genre_display = "\n- ".join([f"'{g}'" for g in info_data.genres])
        console.print(f"\nGenres available:\n- {genre_display}\n\n")

    if show_token and info_data.token:
        console.print("Spotify Auth Token:")
        console.print(Pretty(asdict(info_data.token)), soft_wrap=True)


async def info_logic(email: EmailStr, show_genres: bool = True, show_token: bool = True) -> SpotifyInfoData:
    info_data = SpotifyInfoData()

    async with get_db() as session:
        user_repository = get_user_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound(f"User with email '{email}' not found.")

        if show_genres:
            track_repository = get_track_repository(session)
            genres = await track_repository.get_distinct_genres(user.id)
            info_data = replace(info_data, genres=genres)

        if show_token:
            auth_token_repository = get_auth_token_repository(session)
            token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
            info_data = replace(info_data, token=token)

        return info_data
