import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.enums import MusicProvider


async def discard_oauth_state(user_id: uuid.UUID, provider: MusicProvider, uow: UnitOfWorkPort) -> None:
    async with uow:
        await uow.auth_states.delete(user_id=user_id, provider=provider)
