import uuid

from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.domain.value_objects.blacklist import UserBlacklist


async def list_blacklist(user_id: uuid.UUID, blacklist_repository: BlacklistRepository) -> UserBlacklist:
    return await blacklist_repository.get_all_for_user(user_id=user_id)
