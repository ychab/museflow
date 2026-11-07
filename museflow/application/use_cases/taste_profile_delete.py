import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.exceptions import TasteProfileNotFoundError


async def delete_taste_profile(
    user_id: uuid.UUID,
    name: str,
    uow: UnitOfWorkPort,
) -> None:
    async with uow:
        deleted = await uow.taste_profiles.delete(user_id=user_id, name=name)

    if not deleted:
        raise TasteProfileNotFoundError()
