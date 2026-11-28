from typing import Annotated

from fastapi import APIRouter
from fastapi import Path
from fastapi import Request
from fastapi import Response
from fastapi import status

from museflow.application.inputs.taste import BuildTasteProfileJobInput
from museflow.application.use_cases.taste_profile_build_queue import queue_taste_profile_build
from museflow.application.use_cases.taste_profile_delete import delete_taste_profile
from museflow.application.use_cases.taste_profile_get import get_taste_profile
from museflow.application.use_cases.taste_profile_list import get_taste_profiles
from museflow.domain.const import TASTE_PROFILE_NAME_PATTERN
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import PageParamsDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.schemas import ProblemDetails
from museflow.infrastructure.entrypoints.api.v1.schemas.common import PageResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.jobs import JobResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.jobs import JobResponseAdapter
from museflow.infrastructure.entrypoints.api.v1.schemas.taste_profiles import TasteProfileResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.taste_profiles import TasteProfileSummaryResponse

router = APIRouter()

TasteProfileNamePath = Annotated[str, Path(pattern=TASTE_PROFILE_NAME_PATTERN, description="The profile's name")]


@router.post(
    "",
    name="taste_profile_build",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ProblemDetails,
            "description": "The profile is already built, or a build is already running",
        }
    },
)
async def build_taste_profile(
    *,
    job_in: BuildTasteProfileJobInput,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> JobResponse:
    """Queues the build of a taste profile from the listening history, by an LLM: poll the job it answers until it is
    done or failed, then read the profile by its name.

    A profile still `building` (its job failed, e.g. paused on a rate limit) resumes from its last period saved: send
    the same request again. A profile already built must be deleted first.
    """
    job = await queue_taste_profile_build(user=current_user, job_in=job_in, uow=uow)

    response.headers["Location"] = request.app.url_path_for("job_get", job_id=str(job.id))
    return JobResponseAdapter.validate_python(job, from_attributes=True)


@router.get("", name="taste_profile_list")
async def list_taste_profiles(
    *,
    page_params: PageParamsDep,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> PageResponse[TasteProfileSummaryResponse]:
    """The user's taste profiles, the last updated first, without their data."""
    page = await get_taste_profiles(
        user_id=current_user.id,
        uow=uow,
        limit=page_params.limit,
        offset=page_params.offset,
    )
    return PageResponse[TasteProfileSummaryResponse].model_validate(page)


@router.get("/{name}", name="taste_profile_get")
async def view_taste_profile(
    name: TasteProfileNamePath,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> TasteProfileResponse:
    """A taste profile with its data: partial while its status is `building`."""
    taste_profile = await get_taste_profile(user_id=current_user.id, name=name, uow=uow)
    return TasteProfileResponse.model_validate(taste_profile)


@router.delete(
    "/{name}",
    name="taste_profile_delete",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_409_CONFLICT: {"model": ProblemDetails, "description": "A build of the profile is running"}
    },
)
async def remove_taste_profile(
    name: TasteProfileNamePath,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> None:
    """Deletes a taste profile; the playlists built from it are kept. Rebuilding it takes a full, paid build."""
    await delete_taste_profile(user_id=current_user.id, name=name, uow=uow)
