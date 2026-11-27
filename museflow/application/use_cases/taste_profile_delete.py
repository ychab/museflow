import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.exceptions import TasteProfileBuildInProgressError
from museflow.domain.exceptions import TasteProfileNotFoundError


async def delete_taste_profile(
    user_id: uuid.UUID,
    name: str,
    uow: UnitOfWorkPort,
) -> None:
    """Deletes the profile, unless a build of it is running.

    Raises:
        TasteProfileBuildInProgressError: If a build holds the profile: its next checkpoint would bring it back.
        TasteProfileNotFoundError: If the user has no profile of that name.
    """
    async with uow:
        if await uow.taste_builds.is_held(user_id=user_id, name=name):
            raise TasteProfileBuildInProgressError(f"A build of taste profile '{name}' is running: wait for it to end")
        deleted = await uow.taste_profiles.delete(user_id=user_id, name=name)

    if not deleted:
        raise TasteProfileNotFoundError()
