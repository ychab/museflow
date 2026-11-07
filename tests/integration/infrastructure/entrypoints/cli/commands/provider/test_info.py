import pytest

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.provider.info import provider_info_logic


class TestProviderInfoLogic:
    async def test__user__not_found(self) -> None:
        with pytest.raises(UserNotFound):
            await provider_info_logic(email="ghost@example.com", provider=MusicProvider.SPOTIFY)

    async def test__token__nominal(self, user: User, auth_token: OAuthProviderUserToken) -> None:
        token = await provider_info_logic(email=user.email, provider=MusicProvider.SPOTIFY)

        assert token is not None
        assert token.token_access == auth_token.token_access
        assert token.token_refresh == auth_token.token_refresh
