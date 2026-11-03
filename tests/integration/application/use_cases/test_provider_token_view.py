from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.provider_token_view import view_provider_token
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider


class TestViewProviderTokenUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User, auth_token: OAuthProviderUserToken) -> None:
        token = await view_provider_token(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)

        assert token is not None
        assert token.token_access == auth_token.token_access

    async def test__none(self, uow: UnitOfWorkPort, user: User) -> None:
        token = await view_provider_token(user_id=user.id, provider=MusicProvider.SPOTIFY, uow=uow)

        assert token is None
