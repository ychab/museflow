import uuid

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider


async def view_provider_token(
    user_id: uuid.UUID,
    provider: MusicProvider,
    uow: UnitOfWorkPort,
) -> OAuthProviderUserToken | None:
    async with uow:
        return await uow.auth_tokens.get(user_id=user_id, provider=provider)
