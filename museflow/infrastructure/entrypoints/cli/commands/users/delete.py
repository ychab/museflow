from pydantic import EmailStr

import typer

from museflow.application.use_cases.user_delete import delete_user
from museflow.application.use_cases.user_get import get_user
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.users import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("delete", help="Delete a user account and all of its data.")
def users_delete_command(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if not yes:
        typer.confirm(
            typer.style(
                f"About to delete the user {email} and all of its data: tracks, playlists, taste profiles, blacklist, "
                "provider tokens and LLM usage. This cannot be undone. Continue?",
                fg=typer.colors.YELLOW,
            ),
            abort=True,
        )

    try:
        run_logic(users_delete_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"User {email} deleted.", fg=typer.colors.GREEN)


async def users_delete_logic(email: EmailStr) -> None:
    uow = get_wiring().build_unit_of_work()

    user = await get_user(email=email, uow=uow)

    await delete_user(user_id=user.id, uow=uow)
