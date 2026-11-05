from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderOAuthStateInvalidError
from museflow.domain.exceptions import UserNotFound


async def consume_oauth_state(state: str, provider: MusicProvider, uow: UnitOfWorkPort) -> User:
    """Consumes an OAuth state, single use, and returns the user who started the flow.

    Raises:
        ProviderOAuthStateInvalidError: If the state is unknown, expired, or was issued for another provider.
        UserNotFound: If the user of the state no longer exists.
    """
    async with uow:
        auth_state = await uow.auth_states.consume(state=state)
        user = await uow.users.get_by_id(auth_state.user_id) if auth_state else None

    if not auth_state or auth_state.is_expired() or auth_state.provider != provider:
        raise ProviderOAuthStateInvalidError()
    if not user:
        raise UserNotFound()

    return user
