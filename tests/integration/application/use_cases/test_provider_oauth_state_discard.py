from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_oauth_state_discard import discard_oauth_state
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider


class TestDiscardOAuthStateUseCase:
    async def test__nominal(
        self,
        uow: UnitOfWorkPort,
        user: User,
        auth_state: OAuthProviderState,
        auth_state_repository: OAuthProviderStateRepository,
    ) -> None:
        await discard_oauth_state(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)

        assert await auth_state_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY) is None
