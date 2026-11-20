from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderOAuthStateInvalidError


async def consume_oauth_state(state: str, user: User, provider: MusicProvider, uow: UnitOfWorkPort) -> None:
    """Consumes an OAuth state, single use, which must have been issued to `user`.

    The caller authenticates `user` on its own (the API's Bearer token, the CLI's email): a state alone proves only that
    someone started a flow, not that the person finishing it is the same (#101).

    Raises:
        ProviderOAuthStateInvalidError: If the state is unknown, expired, issued for another provider, or issued to
            another user.
    """
    async with uow:
        auth_state = await uow.auth_states.consume(state=state)

    if not auth_state or auth_state.is_expired() or auth_state.provider != provider or auth_state.user_id != user.id:
        raise ProviderOAuthStateInvalidError()
