import uuid
from dataclasses import replace

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.taste import TasteProfile


async def import_taste_profile(
    user_id: uuid.UUID,
    taste_profile: TasteProfile,
    uow: UnitOfWorkPort,
) -> TasteProfile:
    # The exported profile may come from another user or database: it gets a new id and the importing user.
    taste_profile = replace(taste_profile, id=uuid.uuid4(), user_id=user_id)

    async with uow:
        return await uow.taste_profiles.upsert(taste_profile)
