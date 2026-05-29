import uuid

from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.domain.entities.taste import TasteProfile


async def list_taste_profiles(
    user_id: uuid.UUID,
    taste_profile_repository: TasteProfileRepository,
) -> list[TasteProfile]:
    return await taste_profile_repository.list(user_id=user_id)
