from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_oauth_state_consume import consume_oauth_state
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider


class TestConsumeOAuthState:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
    ) -> None:
        state_user = await consume_oauth_state(state=auth_state.state, provider=MusicProvider.SPOTIFY, uow=uow)

        assert state_user.id == user.id
        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
