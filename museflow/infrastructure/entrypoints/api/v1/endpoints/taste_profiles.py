from typing import Annotated

from fastapi import APIRouter
from fastapi import Path
from fastapi import status

from museflow.application.use_cases.taste_profile_delete import delete_taste_profile
from museflow.application.use_cases.taste_profile_get import get_taste_profile
from museflow.application.use_cases.taste_profile_list import get_taste_profiles
from museflow.domain.const import TASTE_PROFILE_NAME_PATTERN
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import PageParamsDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.schemas import ProblemDetails
from museflow.infrastructure.entrypoints.api.v1.schemas.common import PageResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.taste_profiles import TasteProfileResponse
from museflow.infrastructure.entrypoints.api.v1.schemas.taste_profiles import TasteProfileSummaryResponse

router = APIRouter()

TasteProfileNamePath = Annotated[str, Path(pattern=TASTE_PROFILE_NAME_PATTERN, description="The profile's name")]


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
