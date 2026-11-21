from typing import Annotated

from pydantic import EmailStr

import typer

from museflow.application.use_cases.stats_top_tags_get import TopTagsResult
from museflow.application.use_cases.stats_top_tags_get import get_top_tags
from museflow.application.use_cases.user_get import get_user
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MAX
from museflow.domain.const import DISCOVERY_TRACK_SCORE_MIN
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTier
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.stats import app
from museflow.infrastructure.entrypoints.cli.commands.stats import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption
from museflow.infrastructure.entrypoints.cli.parsers import validate_score_range
from museflow.infrastructure.entrypoints.cli.utils.display import build_ranking_table


@app.command("tags", help="Show top genres, moods or locales ranked by overall score (breadth x depth x quality).")
def stats_tags_command(
    email: EmailOption,
    by: Annotated[EnrichField, typer.Option("--by", help="Tags to rank")] = EnrichField.GENRE,
    tier: Annotated[GenreTier | None, typer.Option("--tier", help="Genre tier to rank (with --by genre only)")] = None,
    source: Annotated[SourceFilter, typer.Option("--source", help="Track source to include")] = SourceFilter.ALL,
    score_min: Annotated[
        int | None,
        typer.Option(
            "--score-min",
            help="Minimum score filter (0-10)",
            min=DISCOVERY_TRACK_SCORE_MIN,
            max=DISCOVERY_TRACK_SCORE_MAX,
        ),
    ] = None,
    score_max: Annotated[
        int | None,
        typer.Option(
            "--score-max",
            help="Maximum score filter (0-10)",
            min=DISCOVERY_TRACK_SCORE_MIN,
            max=DISCOVERY_TRACK_SCORE_MAX,
        ),
    ] = None,
    confidence: Annotated[
        int,
        typer.Option(
            "--confidence",
            help="Bayesian confidence constant: tags with fewer rated tracks than this are pulled toward the mean",
        ),
    ] = app_settings.STATS_BAYESIAN_CONFIDENCE,
    sort: Annotated[RankingSortBy, typer.Option("--sort", help="Ranking strategy")] = RankingSortBy.OVERALL,
    limit: Annotated[int, typer.Option(help="Max rows in the table", min=1)] = 20,
) -> None:
    if tier is not None and by != EnrichField.GENRE:
        raise typer.BadParameter("--tier only applies to --by genre")

    validate_score_range(score_min, score_max)

    try:
        result = run_logic(
            stats_tags_logic(
                email=email,
                by=by,
                tier=tier,
                source=source,
                score_min=score_min,
                score_max=score_max,
                confidence=confidence,
                sort=sort,
                limit=limit,
            )
        )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if result.rankings:
        title = f"Top {by.capitalize()}s" + (f" ({tier})" if tier else "")
        console.print(build_ranking_table(title, by.capitalize(), result.rankings, sort))
    else:
        typer.secho(f"No {by} stats found.", fg=typer.colors.YELLOW)

    if result.unenriched_count:
        typer.secho(f"{result.unenriched_count} tracks without {by} are not ranked.", dim=True)


async def stats_tags_logic(
    email: EmailStr,
    by: EnrichField,
    tier: GenreTier | None,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: RankingSortBy,
    limit: int,
) -> TopTagsResult:
    uow = get_wiring().build_unit_of_work()

    user = await get_user(email=email, uow=uow)

    return await get_top_tags(
        user_id=user.id,
        field=by,
        tier=tier,
        source=source,
        score_min=score_min,
        score_max=score_max,
        confidence=confidence,
        sort=sort,
        limit=limit,
        uow=uow,
    )
