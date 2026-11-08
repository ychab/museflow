import uuid
from dataclasses import replace

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.taste import TasteProfile


async def import_taste_profiles(
    user_id: uuid.UUID,
    taste_profiles: list[TasteProfile],
    uow: UnitOfWorkPort,
) -> list[TasteProfile]:
    # The exported profiles may come from another user or database: they get a new id and the importing user.
    taste_profiles = [replace(profile, id=uuid.uuid4(), user_id=user_id) for profile in taste_profiles]

    # One block: a file is imported whole or not at all.
    async with uow:
        return [await uow.taste_profiles.upsert(profile) for profile in taste_profiles]
